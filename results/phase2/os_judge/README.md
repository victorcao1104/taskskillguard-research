# Actual OS replay Judge supplement

Offline preparation is complete. Run status and all explicit denominators are in summary.json. inputs.jsonl is the complete model-visible evidence; evaluation_targets.json is never sent. Raw responses share results/api/raw and the single-writer results/api/budget.jsonl ledger.

Offline verify/summarize: `.venv/Scripts/python.exe scripts/run_os_judge_phase2.py`.

API execution by the sole ledger owner: `.venv/Scripts/python.exe scripts/run_os_judge_phase2.py --api --env-file <approved-local-env-file>`. The explicit env-file gate applies even when an environment key exists.

The script makes at most three pairs × two models = six calls, saves run manifests before calls, checkpoints each response, and verifies input/request hashes on resume. Existing unresolved rows are retained; rerunning does not silently resample them. No containers are rerun.

This is descriptive agreement with deterministic fixture evaluation, not human ground truth or necessity accuracy. The six responses are clustered within three pairs and two fixture families. No significance inference is made. Core preservation compares the task-requested deterministic output (JSON value equality or exact text). Goal targets come only from authoritative replay_summary_final.json. Unknowns are excluded from agreement denominators and retained as counts; missing and unresolved records are separate.

Input literals are extracted without execution from fixtures() in worker.py only after its hash matches the frozen typed-run manifest. These are frozen setup values, not post-run input snapshots. Captured outputs and raw events are allowlisted. Oracle labels, permission labels, guard decisions, necessity verdicts, sink acceptance classifications and prewritten outcome expectations are excluded from model inputs.
