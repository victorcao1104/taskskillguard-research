# Phase 11 prospective analysis contract

This plan is frozen with production before heldout materialization and before API outcomes. Code implementing summaries may be written after freeze; it may not change these estimands or omit failed cases. Any exploratory addition is labelled and separate. All comparisons describe a finite synthetic benchmark. Intervals reflect resampling structural templates, not real-world deployment uncertainty or formal confirmation of novelty.

## Units and strata

Main cohort: 48 cases/24 families, challenge cohort:24 cases/12 families, each with two lexical variants. Scaling siblings are a separate stratum and never add independent families. API selection is exactly suffix -0, one case per each of 36 distinct families; actual world is `int(sha256('actual11:'+case_id)[:8],16) % world_count`. Models are GPT-6 Luna/GPT-4.1 mini. A row expanded across worlds, budgets or faults is not an independent sample. Primary summaries report main and challenge separately and a clearly labelled 36-family equal-weight aggregate. Family aggregation first averages its variants/worlds for the stated condition, then weights each family equally.

## Fixed deterministic grid

For every main, challenge and scaling case, all actual worlds: original_first, route_cover, observe_cover and seeded random; budgets 2,4,8,12,full; fixed versus certificate stop. A full budget equals the public catalog size. Every returned positive/negative certificate is rechecked against its trusted cache. Every positive is actually executed without fault; unexpected failure aborts acquisition/publication for investigation. This is protocol validation, not deletion of hard cases.

Compare audited world/route execution to independent guarded reference, and to the actual executor with no fault. Record files/emits, success, errors, calls/reuses and steps; any deliberate normalization is documented. Compare old Phase10 controller at quota32/planner512/observation2 with new full observe_cover at quota32; this is an end-to-end **contract** comparison with unequal acquisition/planning access, not an isolated causal repair effect.

Recovery uses full observe_cover certificates only, all main/challenge worlds, twelve predeclared fault schedules: none, ambiguous_after, terminal_noncommit, pending, unavailable, stale, wrong_signature, pending_absent, second_ambiguous_after, second_terminal_noncommit, emit_ambiguous_after, emit_terminal_noncommit. Policies strict_stop, terminal_status, same_id_dedup; status budgets0/1, effect+status quota32. Retain missing-certificate and untriggered-fault rows. Primary recovery contrast uses status budget1 and the two first-mutation terminal faults; show triggered and all-row denominators. Same-ID dedup has a stronger backend capability and is never described as information-matched. Unsafe fresh-ID retry is an explicit toy negative control, not a recommended runtime.

## API and integrated endpoints

288 streams: source/graph/padding online and source fixed, per model/case. Max12 queries, no retries. Online check precedes next request construction/reservation/dispatch. Fresh fixed and online samples are independently acquired; paired family differences include selector variability. Actual recorded calls/tokens/costs and elapsed sums are reported. Cost is a conservative token-rate estimate, not an invoice. Parallel elapsed sums are not campaign wall time. If budget rejection occurs, disclose latency-dependent censoring and every affected family/cell.

Replay every acquired stream's paid prefix at budgets2/4/8/12; same certificate checker and actual execution for faults none/ambiguous_after/terminal_noncommit/pending_absent and three recovery policies. Never invent a missing selection or finish an invalid stream. Fixed/online cells and view/model are kept distinct. The principal model comparator is predeclared observe_cover at the same actual world and query budget; also show route_cover, original_first and random so no weaker baseline is substituted. Report hindsight minimum certificate-query cost from independent reference as privileged lower bound, never as a selectable policy.

Matched-prefix analysis finds the earliest positive certificate within each observed stream prefix and executes its witness as well as the later witness. Report both success, route equality and full result equality separately. Saved query counts are offline counterfactual work; this table is not campaign invoice savings. Actual online/fixed fresh-stream cost differences are the empirical cost comparison.

## Reliability and unknowns

Count decision attempts, pre-I/O budget rejections, uncertain transport/interruption, confirmed provider responses, completed envelopes, valid JSON/schema selections, valid complete streams, and partial paid-prefix success separately. Posthoc Phase10 raw re-audit compares old/new parser only on existing responses; never reconstruct absent later queries or rewrite old streams. API 400/incomplete/refusal/invalid selections remain failures.

Execution status is certified, infeasible, unknown, or observation_mismatch. Compare to independent full-observation class truth: unknown with an available common route is budget-limited certifiable; unknown without one is unresolved robust infeasibility. A returned negative is known infeasibility for the robust fixed-route contract, not unknown and not necessarily actual-world impossibility. Availability failures are a separate cause and are not intrinsic ambiguity. Input catalog violations and state drift are explicit assumption counterexamples.

## Comparisons and uncertainty

Primary descriptive contrasts: (1) observe_cover online vs fixed, query count and completion, all budgets; (2) each model source-online vs observe_cover at budget12, certified fault-free completion and query cost; (3) terminal_status vs strict_stop, terminal faults/status1. Secondary: graph-source, graph-padding, source-online-source-fixed, alternate heuristics, cohort interactions, scaling and old-contract comparison. Report paired wins/losses/ties and each family effect. Bootstrap paired family effects with 10,000 samples seed11101; give 2.5/97.5 percentiles. No p-values, significance labels, multiplicity-adjusted confirmatory claims or population-generalization claim are made. All intervals are exploratory/descriptive, including primary contrasts.

Work counters remain a vector: acquired queries, interpreter calls/steps, initial observation calls, certificate pair checks and observation comparisons, actual effect/status calls, API tokens/dollars and latency. Selector partition/structural scoring, parsing, standalone verifier CPU and OS overhead are excluded from the abstract counters. Do not call a weighted sum total compute or latency. Actual API elapsed time is distinct from deterministic operation counts.

## Release requirements

Independent first-pass hashes and chronology; full references and structural audit; all failures; isolated no-network replay; full tests; offline source/raw/ledger/certificate/reference verification; unchanged37907 baseline files; new release hash manifest; exact private remote commit CI; reproducible figure tables and paper claims mapped to evidence. A paper draft must state closed finite-world, trusted snapshot/gateway/status, synthetic-only and tokenizer/single-run limitations. Prior-art mechanisms are cited and no model/graph superiority is presumed.
