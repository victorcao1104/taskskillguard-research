# Independent read-only review

The reviewer checked the frozen request and budget layer, adaptive design and common protocol. It found no blocker for paid acquisition and confirmed the $19.49682 planned reservation ceiling under the $20 hard cap. Requests have distinct campaign, method, case, model, replicate and iteration identities. Orphan dispatches are not resent.

Three reporting/reproduction issues were identified and addressed outside the frozen method:

1. Cached Provider reads lacked an identity assertion. The separate `reproduce.py` preflight recomputes fingerprints from complete raw request bodies and replicate IDs and checks saved identities, filenames and dispatch markers before replay.
2. A replay directed at existing outcomes only reloads them. The recommended reproduction entry point requires a fresh output directory, recomputes every episode and compares semantic records and trace hashes.
3. The legacy `model_calls` field includes pre-dispatch byte-cap failures. Analysis names it `provider_invocations` and separately counts saved request/response identities. All failures remain in the outcome denominator. Costs come from the append-only ledger, not the invocation counter.

The reviewer ran 52 tests (two filesystem tests excluded by its environment) and in-memory probes, without API calls or source/data changes. The root run passed all 54 tests. The review did not certify novelty, empirical claims or unbounded safety. Catalogue preparation, limited adaptive search and protocol amendment timing remain explicit limitations.
