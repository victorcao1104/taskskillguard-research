# Independent pre-acquisition review

A separate read-only reviewer inspected the interpreter, declarative truth checks, source transformer, compiler, generator, verification, shared protocol, budget adapter and campaign orchestration before development requests. It did not make API calls, edit files or supply experiment answers.

Findings fixed before the first paid v14 request:

1. Conditional expressions, Boolean operations, comprehension filters, sort keys, nonlocal loop control and secret-dependent exceptions could lose control labels. Regression probes reproduced the bypasses. Secret observations now conservatively contaminate the rest of a continuation; saved-value and existence-label retrieval are covered too.
2. Nested containers could grow exponentially despite the AST step bound. Expanded value structure is now bounded before copies; string formatting is excluded.
3. Initially applying every saved value's label to its name penalized the source-free compiler. The common cache view now excludes secret-observation-dependent prefix caches for every method. This is conservative and may discard useful work.
4. Counterexamples initially carried hidden secret and physical-commit fields. They remain in audit evidence but are removed from model feedback.

Independent recheck: 32 tests passed, and 3,456 compiler/state validation world runs passed across six families and seven feasible conditions. All reproduced control-flow/allocation probes were blocked. The remaining allowance and complete-grid reservations were checked. No blocking finding remained before development acquisition.

After the complete development pilot, all main methods received the same system-level tool clarification and larger input ceiling. The pilot and old source remain archived. No task solution was added.

An independent interpretation review then approved the additive distinction between blocked recovery, forced benign reconstruction and actual normal pass-through. It separately checked 792 benign original world runs. See `reporting_amendment.md` for the reporting rules. These reviews are bounded code/evidence checks, not a production sandbox proof or a novelty certification.
