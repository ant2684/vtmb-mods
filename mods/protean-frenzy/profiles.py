"""Required final exact-byte gameplay scenarios; resources are separate batches."""
BASE=['actions','morph-visual','native-edges','feeding-entry','idle-races','latest-interface','latest-midload','latest-walk','latest-ui','inventory-2','frenzy','frenzy-frenzy-first','frenzy-melee','transitions','feeding-expiry','feeding','feeding-middle','feeding-release','stealth-visual','save-active','restore-active','restore-legacy']
NATIVE_HUNGER=['native-hunger-human','native-hunger-human-outputs','native-hunger-warform','native-hunger-warform-outputs','native-hunger-claws2','native-hunger-katana','native-hunger-tiger']
DEFAULT=NATIVE_HUNGER+BASE+['claws-actions-male','claws-actions-female','stealth-tiger','filter-save','filter-restore']
REQUIRED=DEFAULT+['native-hunger-warform-melee-off','frenzy-maps-library','frenzy-maps-griffith','native-dependencies-off']
