# Acquisition incident and prospective recovery rule

The strict supplement was frozen at `2a6a87bfd`. Its first process stopped after
some jobs could not save request metadata at a 263-character Windows path. A
small filesystem probe reproduced failure with ordinary addressing and success
with the extended-length Windows prefix. `windows_long_paths.py` addresses the
same files with that prefix; it changes no frozen source, prompt or interpreter
semantics.

The resumed process completed the first 512-episode grid, but 744 requests in
372 episodes had `transport_error` / `URLError`. A credential-free probe in that
environment returned DNS `getaddrinfo failed`. There was also one separate API
`invalid_prompt` response. These observations are not model-semantic failures.
Every first-acquisition episode, request and failure remains available under
`results/strict_state/` and `api/`.

Before obtaining recovery answers, commit `d3d46c656` froze a rule: reacquire a
whole episode if and only if it contained at least one transport error; retain
all other episodes, including semantic failures and the API rejection. Each
reacquired episode has the same protocol, permissions, validation, task, and
two candidate slots. Its request IDs use `strictretry`. New answers are separate
draws and are not pooled with old answers as independent task replications.
The output used for the controlled-state analysis is explicitly stored under
`results/strict_state_recovered/`.

The 372 affected episodes admitted at most $6.6368 of additional reservations
against $9.894256175 remaining. All prior unknown-billing reservations remain
charged conservatively. No balance was reset. Live recovery uses an environment
that can reach the API. A fresh transport error opens a circuit breaker and is
not automatically retried. Ordinary semantic, syntax and API failures still
count. This recovery excludes an environmental alternative explanation; it
does not improve or tune the recovery method using failed model answers.

The initial transport batch should have been stopped earlier. The new runner
starts with a single real request and stops additional work on a transport
failure. The original interruption and budget exposure remain part of the
record rather than being silently removed.

The recovery subsequently saved 511 of 512 episodes. A model-generated `get`
call on a string raised an uncaught `AttributeError` in the interpreter. Commit
`efd3f807b` records a separate adapter that classifies this as the existing
`MALFORMED_PROGRAM` failure, with a regression test and hashes. Frozen files
remain unchanged. The first answer had already been cached. After automatic
approval rejected a batch resume due to possible duplicate-request exposure,
`finish_one_episode.py` verified the exact missing-ID set and finished only that
episode, allowing at most one new Luna request ($0.004 maximum reservation).
No other episode was reacquired. All 512 corrected episodes were then reexecuted
locally with the adapter; their recorded outcomes and traces matched.
