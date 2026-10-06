"""Build in isolated artifacts; verify the exact candidate, not a substitute."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from infra.core import ROOT, Blocked, catalog, digest, need, require, run, sha
from infra.release import clean_pe, members


def environment(config, work):
    return {'PYTHONPATH': os.pathsep.join(filter(None, [str(ROOT), config.get('dependencies',''), os.environ.get('PYTHONPATH','')])),
            'ZIG_GLOBAL_CACHE_DIR': str(ROOT/'.local/cache/zig-global'), 'ZIG_LOCAL_CACHE_DIR': str(work/'zig-local')}


def scratch(work):
    source = work / 'source'
    shutil.copytree(ROOT / 'mods', source/'mods', ignore=shutil.ignore_patterns('build','__pycache__'))
    shutil.copytree(ROOT / 'infra/common', source/'infra/common')
    return source


def compile_c(zig, source, output, env, extra=()):
    return run([zig, 'cc', '-target', 'x86-windows-gnu', '-O2', '-g0', '-s', '-Wall', '-Wextra', '-Werror', *extra, '-o', output, source], timeout=240, env=env)


def build(mod, config, source, work):
    if os.name!='nt':raise Blocked('Native build/load verification requires Windows')
    info = catalog()['mods'][mod]
    zig = need(config, 'zig')
    version = run([zig,'version'], timeout=15).strip()
    require(version == '0.15.2', 'Pinned Zig 0.15.2 required; found ' + version)
    env = environment(config, work)
    code = source / 'mods' / mod
    if mod in ['protean','subtitle']:
        headers=list((code/'plugin').glob('generated_*.h'))
        recorded={p.name:p.read_bytes().replace(b'\r\n',b'\n') for p in headers}
        run([sys.executable,'-B',code/'tools/generate_blobs.py'],env=env)
        for name,raw in recorded.items():
            generated=code/('tools/'+name if mod=='subtitle' else 'plugin/'+name)
            require(generated.read_bytes().replace(b'\r\n',b'\n')==raw,'Generated native helper disagrees with its current source: '+name)
    output = code / 'build' / info['filename']
    output.parent.mkdir(parents=True, exist_ok=True)
    native = next(code.glob('plugin/*.c'))
    extra = ['-shared']
    if mod == 'history':
        headers = Path(zig).resolve().parent/'lib/libc/include/any-windows-any'
        extra += ['-nostdlib','-isystem',str(headers),'-Wl,--entry,DllMain@12','-lkernel32']
    compile_c(zig, native, output, env, extra)
    finalizer = code/'tools/finalize_pe.py'
    if not finalizer.exists():
        finalizer = code/'tests/finalize_pe.py'
    run([sys.executable,'-B',finalizer,output], env=env)
    clean_pe(output.read_bytes(), info['exports'], mod)
    return output, code, env


def synthetic(mod, config):
    with tempfile.TemporaryDirectory(prefix='vtmb-ci-') as td:
        work = Path(td)
        candidate, code, env = build(mod, config, scratch(work), work)
        frozen = digest(candidate)
        loader = code/'build/load_clean.exe'
        compile_c(need(config,'zig'), code/'tests/load_clean.c', loader, env)
        logs = [run([loader,candidate,export],env=env) for export in catalog()['mods'][mod]['exports']]
        harness = code/'tests/native_harness.c'
        if harness.exists():
            exe = code/'build/native_harness.exe'
            compile_c(need(config,'zig'), harness, exe, env)
            logs.append(run([exe],env=env))
        require(digest(candidate) == frozen, 'CI candidate changed after finalization')
        return {'sha256': frozen, 'checks': logs, 'scope': 'Own source build, clean PE, relocated native Windows load and available synthetic installation harness; no game fixtures/acceptance'}


def source_identity(mod):
    paths = list((ROOT/'mods'/mod/'plugin').glob('*'))
    paths += list((ROOT/'mods'/mod/'tools').glob('*.py'))
    paths += list((ROOT/'infra/common').glob('finalize_pe*.py'))
    return {p.relative_to(ROOT).as_posix():digest(p) for p in sorted(paths) if p.is_file()}


def exact(mod, config, candidate=None):
    info = catalog()['mods'][mod]
    game = Path(need(config,'game_root'))
    for relative, pin in catalog()['native_modules'].items():
        path = game/relative
        if not path.is_file():
            raise Blocked('Missing native fixture: ' + relative)
        if digest(path)!=pin:raise Blocked('Unsupported native module: '+relative+'; select the pinned supported installation')
    with tempfile.TemporaryDirectory(prefix='vtmb-exact-') as td:
        work = Path(td)
        source = scratch(work)
        code = source/'mods'/mod
        (code/'build').mkdir(exist_ok=True)
        if candidate:
            external = Path(candidate).resolve()
            if not external.is_file():raise Blocked('Candidate file absent: '+str(external))
            frozen = digest(external)
            rebuilt, _, env = build(mod, config, source, work)
            require(digest(rebuilt) == frozen, 'Candidate does not match this checkout and pinned finalized build. Use its matching source checkout; never bypass this gate.')
            plugin = external
            provenance = {'source':source_identity(mod),'rebuilt_sha256':digest(rebuilt),'compiler':'Zig 0.15.2','mode':'candidate'}
        else:
            archive=Path(need(config,'releases'))/info['archive']
            if not archive.is_file():raise Blocked('Frozen archive absent: '+info['archive'])
            files = members(archive)
            plugin = code/'build'/info['filename']
            plugin.write_bytes(files['Bin/loader/'+info['filename']])
            frozen = digest(plugin)
            require(frozen == info['plugin_sha256'], 'Frozen release identity mismatch')
            env = environment(config,work)
            provenance = {'mode':'frozen release','sha256':frozen}
        clean_pe(plugin.read_bytes(),info['exports'],mod)
        zig = need(config,'zig')
        logs=[]
        if mod in ('console','protean','frenzy'):
            logs.append(run([sys.executable,'-B',code/'tests/verify_exact.py','--plugin',plugin,'--zig',zig,'--game',game],env=env,timeout=600))
        else:
            load = code/('tests/load_clean.exe' if mod == 'subtitle' else 'build/load_clean.exe' if mod=='history' else 'build/load-clean.exe')
            compile_c(zig,code/'tests/load_clean.c',load,env)
            logs += [run([load,plugin,export],env=env) for export in info['exports']]
            if mod == 'history':
                logs.append(run([sys.executable,'-B',code/'tests/verify.py',plugin,game/'Vampire/dlls/vampire.dll'],env=env,timeout=600))
                if candidate:
                    logs.append(run([sys.executable,'-B',code/'tests/verify_pool.py',plugin,game/'Vampire/cl_dlls/client.dll'],env=env,timeout=120))
            elif mod == 'background':
                exe = code/'build/native-harness.exe'
                compile_c(zig,code/'tests/native_harness.c',exe,env)
                logs.append(run([exe],env=env))
                logs.append(run([sys.executable,'-B',code/'tests/verify.py','--client',game/'Vampire/cl_dlls/client.dll','--plugin',plugin,'--dependency-dir',config.get('dependencies') or work],env=env))
            elif mod=='subtitle':
                exe = code/'tests/native_harness.exe'
                compile_c(zig,code/'tests/native_harness.c',exe,env)
                logs.append(run([sys.executable,'-B',code/'tests/verify.py','--game',game,'--plugin',plugin],env=env,timeout=600))
            else:
                raise Blocked('Implement the future family exact-binary verifier before certifying '+mod)
        require(digest(plugin) == frozen, 'Candidate changed during exact verification')
        return {'sha256':frozen,'provenance':provenance,'checks':logs,'scope':'Exact finalized binary; local pinned native fixtures, ABI, functional guards and rollback; no game launch'}
