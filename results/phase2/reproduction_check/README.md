# Independent replication CLI check

Four fresh CSV oracle-policy containers validated the portable `replay_os_release.py` entry point. All four completed the task; both unguarded runs recorded the expected optional unauthorized write and both guarded runs blocked it. No API calls were made.

This directory is a byte-preserving archive of `work/replica-check`. Embedded `evidence_path` values retain that original location; equivalent evidence is archived under this directory's `runs/`. These four QA observations do not enter the published 240-run experiment or 65-run source/replay denominator. `replication_manifest.json` records the image, input, contract and script hashes.
