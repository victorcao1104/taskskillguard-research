# Independent review and resolution

A fresh-context reviewer inspected the implementation, acquisition boundaries,
analyses and final claims. The main actionable finding was that the first state
experiment allowed effects code to recompute from input. This was disclosed,
all original results were retained, and a separately frozen enforced-computation
supplement was acquired. Review then verified isolation of solver locals,
cache reuse and boundary stops, and hashes of the frozen code.

The reviewer independently checked the later environment-recovery rule: 372
episodes selected solely by transport failures, all 744 original transport
reservations preserved, $6.6368 worst-case recovery admission, and sampled
replacement prompt/schema equivalence. The one candidate type-error escape was
handled by a separate frozen adapter; both target candidates still failed and
their replay signatures matched.

Final review independently reproduced all six strict-state paired contrasts,
the reported group counts and key failure decompositions. It reconciled the
ledger hash and $6.3376851 new upper exposure, and found no remaining substantive
inference or financial defect. A wording correction replaced “one model draw”
with “one recovery episode, up to two candidate slots”; a recovery episode can
make zero to two model requests. Limits on broad superiority, real-world
transfer and novelty remain explicit.

Verification: 55 tests and 1,072 subtests passed. The main and strict saved
programs replayed across 24,042 and 20,512 worlds respectively, with no API
requests. This review is an implementation/evidence check, not independent
human annotation, peer review or external benchmark validation.
