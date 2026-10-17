# Operational failures and complete-group handling

## Network-restricted adaptive launch

The normalized main experiment completed with actual model responses. A subsequent adaptive launch was inadvertently started in a default process without outbound access. All 96 adaptive episodes produced one `transport_error` / `URLError` each, with no model answer. The entire batch remains under `results/robust_adaptive/`. Its reservations remain in the conservative budget ledger; no assertion of zero billing is made.

The adapter's generic protocol rejection obscured the immediate network cause in episode termination labels. Inspecting raw records established the uniform transport failure. A separately frozen wrapper, `adaptive_network_rerun.py`, changes only campaign identity and output location; prompts, tools, permissions, state correction, normalizer and checker are unchanged. All 96 conditions were rerun in a process with outbound access, without selecting by method or success.

## Windows path limit during the rerun

The long worktree path plus `robust_adaptive_network` and the longest case names exceeded the host's filename limit for trace output. Ninety episodes were already saved; six could not save their long trace filenames. The worker pool had completed and cached their model requests before the process exited. Existing saved files were copied byte-for-byte to the shorter `results/adaptive_net/` directory, and the full run resumed there. Saved responses were reused; the budget exposure was unchanged by this resume. All 96 final episodes are in `adaptive_net`; partial original-path files remain as duplicates, not additional independent observations.

The frozen wrapper retains its original default output path. The portable command explicitly supplies the shorter directory. Fresh reproduction also explicitly supplies its output directory; on Windows a short absolute output path is recommended.

Two preliminary wrapper launches failed before execution because its file was initially added at the worktree root rather than the study directory. It was moved into the study before freezing or executing it. Those launch errors made no provider requests and changed no experimental outcomes.

## Strengthened tool-language control

After normalized results were inspected, mini replanning showed many `MISSING_VARIABLE` counterexamples: resource paths were supplied where an existing variable was required. The complete paired `typed_roles` grid adds the same task-independent operand explanation to the full method and source-free model planner. The only example reads an unrelated example path and projects an unrelated example column. It supplies neither a test-specific route nor task data. All 24 cases, both models and three runs are included. It is explicitly post-observation, and all earlier results remain.

This addition is intended to challenge a favorable explanation of the proposed method, not to obtain a preferred result. It uses the same parser, verifier, grants and candidate slots. The response cap and conservative input cap are unchanged; any new cap failures remain failures. Its full reservation bound was admitted before acquisition under the same $20 ledger.

## Final packaging checks

A repeat test command in the restricted process passed 63 tests but could not create the default temporary directory for three fixtures. Rerunning all tests with `--basetemp work/v13-release-tests` passed all 66; the successful output is `reproduction/pytest_release.txt`. This was a host-directory setup failure, not a failed experiment or a source change.

The repository explicitly preserves bytes with `* -text`. The default whitespace checker therefore reports original CRLF line endings as trailing whitespace. The publication check uses Git's `cr-at-eol` setting instead of rewriting the append-only ledger or any frozen artifact. Source hashes, inherited ledger-prefix hash and release file inventory are verified before publication.

The compiler's saved log contains one package-generated trailing space after `Package: algpseudocode`. The staged style check initially stopped on it. The original log is retained and excluded only from whitespace style checking; it remains included in the file-hash inventory and credential-format scan.
