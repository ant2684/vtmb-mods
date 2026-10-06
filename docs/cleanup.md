# Preservation and cleanup

Current gameplay/source archives and original game backups remain protected.
The prototype is excluded. Old Console/Subtitle task directories are enumerated
in a private ledger; all their files, first failures, unique sources, logs and
rollback copies are preserved before deletion.

Preservation verified 2597 files in a recoverable ZIP, checking CRC, raw safe
paths, extraction and every restored SHA-256. Backup/original subtrees also
have independent verified copies. A failed initial archive attempt ran out of
space; only its incomplete task-created output was removed, with every source
still present. The completed archive was created on another volume.

Deletion requires a published source/test commit, successful isolated public
checkout, six independent source export tests, recovery fault checks and an
unchanged preservation ledger. Only those explicit legacy directories are
removed. Existing evidence archives, personal saves/configuration, game rollback
backups, current delivery and excluded prototype are retained. Afterwards all
18 frozen archives are rechecked. Private paths, raw logs and the full deletion
ledger are local evidence, outside the public repository.


The enumerated legacy-directory deletion completed on 2026-10-06 after the
published a4b899a checkout passed all 15 offline rows, six standalone exports
passed, preservation checks passed and hosted CI succeeded. A readonly legacy
copy initially stopped deletion; its bytes had already been independently
archived and verified. The resumed cleanup recorded that first failure and
removed only confirmed remaining files. All 18 current release/source ZIPs
passed the final identity check afterwards. A later gameplay session has its
own recovery status and does not replace this completed cleanup ledger.
