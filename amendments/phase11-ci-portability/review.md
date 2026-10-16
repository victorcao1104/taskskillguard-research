# Independent review of the CI portability amendment

Review basis: original research release `088af27ebdbd1e12037d17fcffd80c4abb9926b4`, the new root test-collection policy, its five tests, the amendment explanation, the frozen Phase 11 workflow, and the retained initial Phase 3 failure log. This review concerns test-environment portability; it is not a new evaluation of the research findings.

**Verdict: the narrow optional-dependency treatment is acceptable, subject to the final amendment manifest and successful full Phase 11 checks on the published commit. It does not justify treating the reduced legacy test environments as full scientific reproduction.** Those publication gates were still pending when this review was written.

## Evidence inspected

The preserved failure log identifies exactly the three listed acquisition tests failing at the lazy `import tiktoken` in `run_phase11.tokenizer()`, each with `ModuleNotFoundError: No module named 'tiktoken'`. The historical workflow installs only `configs/requirements-lock.txt`; the tokenizer is pinned separately in `configs/phase5-requirements.txt`. This supports the stated dependency-integration diagnosis. It does not turn the failed initial run into a successful run, and that failure remains part of the record.

The reviewed root policy has SHA-256 `07f6396094f609e550166588649675297240aeea95b68e398ebce6f85e3ff98d`. The reviewed optional-policy tests have SHA-256 `fb985643e9f1e293c60a4e7d169bca8ac9e057e2ec8414cc2bf12e305ec2d8f3`. The retained representative failure log has SHA-256 `4d3516c329691c559681f90ffbd3d3b6cee1f5adaed9b8c0737fb20b87b1ddee`.

I independently exercised the actual collection hook with controlled dependency discovery and fake collected items. These checks passed:

- Missing optional package marks exactly the three complete node IDs; another test in the same file and a matching function name in a different file are unaffected.
- `--require-tokenizer` with a missing package raises a collection error.
- The exact dedicated Phase 11 workflow name with a missing package raises a collection error.
- A discoverable package adds no skip markers, including in the legacy workflow context.
- An exception from dependency discovery propagates; it is not converted into a dependency skip.

The package-presence branch does not import or execute the package. Any later import, tokenizer-cache, hash, or assertion failure in the original tests therefore remains a failure. The added test also exercises propagation of an `ImportError` from the discovery path. No test body, expected output, production function, or recorded request is patched by the hook.

Independently hashing the existing files confirmed all **8,115 files covered by the Phase 11 release manifest** and all **37,907 baseline files** remain unchanged. Both release-manifest files also matched the committed release. The 8,117 added release files mentioned in the amendment consist of those 8,115 covered files plus the two non-self-hashed release manifests.

## Why this is not a substitute for full coverage

The unchanged dedicated workflow installs the extra pinned requirements, explicitly imports the tokenizer during setup, runs the tests, and then runs the frozen offline verifier. That verifier requires the expected tokenizer version/cache and reconstructs every recorded request. A dependency skip in a legacy job cannot make that separate reproduction gate pass.

The three affected tests protect real properties: stopping before another dispatch, retaining a paid prefix after failure, and the local graph/padding token control. Their absence from a legacy environment is a coverage reduction and must remain visible. The amendment correctly discloses this, preserves initial failures, and does not claim those tests ran in an environment lacking their dependency. The legacy jobs already have other historical skips; only the three additional skips introduced by this amendment should be attributed to this policy.

## Release requirements

The final amendment manifest must include the root policy, its tests, this review, the explanation, `initial_failure.log`, and `initial_ci.json`, and bind them to the original release-manifest hash. These new files are intentionally outside the frozen release inventory and must not be presented as already covered by its original manifest.

Publish success only after the new commit's required checks finish successfully, with the dedicated Phase 11 jobs running the tokenizer-dependent tests and full offline verifier. Retain the earlier failed CI records. Later result snapshots should be additional evidence, not replacements for the original logs. No additional model requests or experiment modifications are required for this correction.
