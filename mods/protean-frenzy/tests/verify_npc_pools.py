"""Compare NPC pools with the unhooked native collector, without a game process."""
import os,json,struct,hashlib,subprocess
from pathlib import Path
cfg=json.loads(Path(os.environ['PFI_CONFIG']).read_text());out=Path(cfg['output']);game=Path(cfg['game'])
root=out/'npc-pool-inputs';root.mkdir(exist_ok=True)
targets={
 'models/character/shared/male/claws.mdl':('male-claws.mdl','c7b515d36d2b5dab50bd2eea178e2e455a589ef35359b565cfcf9e95e726fac8'),
 'models/character/shared/female/claws.mdl':('female-claws.mdl','31e39caabb6ef2528d3cdab41a9bffb16c3d127fbfb5ce9bdc430c0290c0055c'),
 'models/character/shared/male/fists.mdl':('male-fists.mdl','7d0141f5eb4ff44701ffa15ebf0223850a7a92aaab8e72094d09be10c4e6ace2')}
with (game/'Vampire/pack001.vpk').open('rb') as f:
 f.seek(-9,2);count,off=struct.unpack('<II',f.read(8));f.seek(off);index=f.read();q=0
 for _ in range(count):
  n=struct.unpack_from('<I',index,q)[0];q+=4;name=index[q:q+n].decode().lower();q+=n;o,n=struct.unpack_from('<II',index,q);q+=8
  if name in targets:
   dest,digest=targets[name];f.seek(o);data=f.read(n)
   assert hashlib.sha256(data).hexdigest()==digest,('Unsupported original model',name)
   (root/dest).write_bytes(data)
assert all((root/dest).exists() for dest,digest in targets.values())
models=out/'Components/ClawsModels/Unofficial_Patch/models/character/shared'
cmd=[out/'build/exact_npc_pools.exe',out/'Payload/Bin/loader/protean-frenzy-improved.vtm',game/'Vampire/dlls/vampire.dll',models/'male/claws.mdl',root/'male-claws.mdl',models/'female/claws.mdl',root/'female-claws.mdl',root/'male-fists.mdl']
subprocess.run([str(x) for x in cmd],check=True)
