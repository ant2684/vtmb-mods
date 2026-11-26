# Protean & Frenzy Improved 1.4

You can enter Frenzy while Protean 5 is active. Version 1.4 also restores your
weapon and view after a Protean 5 transformation and improves the sound and
blood effects of Claws sneak attacks. The complete package includes revised
Claws combat and the Library and Griffith Park maps with Frenzy enabled.

[Download the game and source packages](https://github.com/ant2684/vtmb-mods/releases/tag/protean-frenzy-v1.4)
or read the [1.4 release notes](../../docs/protean-frenzy-1.4.md). The game ZIP
contains installation, settings and uninstall instructions in `README.txt`.

## Build and regressions

Use Python 3, Zig 0.15.2, pefile, capstone and unicorn. Supply your own 32-bit
Bloodlines game with Unofficial Patch 12.0 and Game Mod Loader. Copy
`local.example.json` to `local.json` in this directory and set the paths to your
game, tools and a separate output directory.

```powershell
python -B build.py --config local.json
python -B run_tests.py --config local.json --suite all
```

For release validation, use the finalized VTM from the game ZIP under
`Payload/Bin/loader` in the configured output directory. Build individual test
programs with `build.py --tests-only` to preserve that VTM. Model tests need the
matching male and female Claws models from the game ZIP in
`Components/ClawsModels` using their game-relative paths, plus the earlier
player-combo source models pinned in `tools/compact_models.py` under `inputs`.
The loader-size regression uses one of the versions pinned in its fixture.

`build_resources.py` and `build_maps.py` generate the base resources from the
specified original inputs. The source asset attached to the release includes
the finisher resource generators and a script to assemble the game ZIP from
the matching finalized inputs. Original retail resources and test saves remain
local. The gameplay runner uses local saves and restores the game after each run.
