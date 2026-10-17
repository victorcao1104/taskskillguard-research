# Implementation and verification plan

1. Archive current commit; hash every previously tracked file; verify reused
   extraction, truth and recovery tests. Keep temporary-path failures as logs.
2. Define and test `adapter.compile_bundle(case)` and `compile_script(text,file)`:
   exact entry selection, source spans, supported control/data semantics, explicit
   rejection. Add no host execution capability.
3. Independently implement `reference.run(source,file,world,goal,suppress=None)`
   over Python AST and `fixtures.build_cases()`. Reference author must not read
   production adapter/runtime or model outcomes. Freeze production before reading
   evaluation fixtures. Audit complete traces, intervention and source coverage.
4. Implement `runtime.execute(case,mode,fault,allowed_ids=None)` with per-effect
   trusted scope and source-flow checks, shared receipts/quota, and two equally
   capable recovery selectors. Tests exercise forgery, data laundering, all-block,
   unauthorized prerequisites, irreversible effects and ambiguous outcome stops.
5. Freeze grid and model protocol; run deterministic/source/intervention grids;
   run bounded fresh two-model source/graph audits only after budget reservation;
   preserve all raw answers and failures; integrate model gates separately.
6. Replay bounded programs in restricted containers. Independently recompute
   counts and matched comparisons; label correlated conditions and case families.
7. Rewrite report around Skill security, not generic stopping theory. Build figures
   from retained results, verify citations, numeric claims, page count and layout.
8. Verify old file hashes, all new tests, offline reproduction, artifact manifest
   and secret hygiene. Commit/push additive branch and tag, publish new release;
   attach PDF/source ZIP and verify remote identity. Report actual costs and limits.

Review focus: unsupported source silently treated safe; instruction-text claims
changing authority; labels lost through intermediate files or branch control;
recovery gaining hidden information or free attempts; a protected zero counter
being presented as an independently measured real-world attack success rate;
post-hoc repairs being called fresh held-out evidence.
