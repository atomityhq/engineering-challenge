# Task 6: deterministic offline G2 evidence/current-validity gate

Prepared PR description only; this file does not create or publish a pull request. The corrected-snapshot isolated rehearsal passed all **96 tests**. A local commit is user-authorized; pushing and opening the actual PR require separate authorization. Rehearsal evidence describes the tested snapshot, not certification of an already committed checkout.

## Summary and scope

Implement Task 6 only in `src/task-6_saijaz/`: typed input/output contracts, strict validation, pure hard/temporal checks, provisional scoring, ordered decisions, three-case sensitivity comparison, CLI, generated examples and local tests. Read the original `fixtures/g2-cases.json` in place; do not copy/change it. Exclude visuals, writing quality, engagement, publishing, cloud services and the other challenge tasks.

## Evaluation and hard checks

Validate envelope, exact metadata fields/types, dates/enums, duplicate keys and finite numbers. Frozen/slotted constructors check invariants rather than relying solely on annotations. Evaluate support, absence of supersession, absence of promotion and absence of unresolved conflict before scoring. Either supersession assertion establishes replacement; disagreement remains visible. Supported plus contradiction yields unknown support, whereas explicit unsupported remains 0. Every finding is preserved.

Decision priority is reject (prohibition), revise (known repairable defect), human_review (unknown/conflicting/inconsistent evidence, failed floor or threshold), then pass. Mandatory failures cannot be overridden by weights. Promotion rejects for every source. Generic competitor information requires independent original evidence/review even under permissive numerical policy. No out-of-scope/revision-limit/exception policy is invented without input contracts.

## Freshness and applicability

Use fixed fixture as_of 2026-10-06, never the system date. News uses event age 0–30 inclusive when status is resolved; >30 needs revision regardless of asserted current status, retaining unknown/incompatible-status findings. This is the fixture's demo convention, not a validated universal threshold. Publication/verification dates do not replace unknown event dates. Old regulations remain valid if asserted current and effective on/before as_of, without supersession/inconsistency. Adopted future rules can be temporally valid while currently_applicable is false; effective date must be strictly after as_of. Missing/inconsistent timing routes to review unless known invalidity takes precedence. News legal applicability is not_applicable, not an unknown scoring input. No verification expiry is invented; future verification creates uncertainty unless known temporal invalidity already takes precedence.

## Criteria, anchors and numerical policy

- Support: 0 explicit unsupported; 0.5 explicit partial support (not representable/emitted in minimum schema); 1 supported without conflict; null supported plus unresolved contradiction.
- Authority: 0 no independent claim authority/competitor; 0.5 reputable secondary; 0.75 official indirect; 1 primary issuer/originating announcer; null unknown relationship.
- Temporal: 0 known invalid/stale/superseded; 0.5 qualified period/scope (not representable/emitted); 1 appropriate event/current/future description; null required timing missing/inconsistent.

The support and temporal 0.5 meanings above are conceptual anchors only: the current typed schema cannot express the required partial-support or qualified-scope assertions. Their implemented values are 0, 1 or null. Authority 0.5 is implemented for reputable secondary reporting. Extending those inputs would require explicit contracts and tests; unknown information is never treated as partial support.

Selected weights (support, authority, temporal) are (0.45,0.30,0.25). Grounding receives the greatest preference, authority distinguishes provenance, and timing retains explicit gate protection instead of being compensated by averaging. Floors are (1,0.5,1); threshold is 0.80 inclusive. Policy g2-demo-v1 and weights grounding-first-v1 are explicitly **uncalibrated**.

Threshold is a conservative preference, not fitted from expected labels. With support/timing 1, selected score is 0.70 + 0.30 × authority; authority floor dominates its threshold, a deliberate disclosed redundancy. Authority-heavy weights expose a nonredundant threshold effect. Scores are not correctness probabilities or scientific measurements.

Every criterion is required, including at zero weight. Unknown/blocking facts produce null aggregate and inspectable reasons; never default unknown to 0/0.5. Eligible scores use full-precision math.fsum. Weights are finite/nonnegative and sum to 1 within absolute tolerance 1e-9; no normalization. Thresholds/floors receive no tolerance. A tolerated sum >1 producing aggregate >1 fails explicitly rather than clipping.

## Sensitivity and fixtures

Three distinct submission-owned synthetic cases assert reputable-secondary, official-indirect and primary relationships; no prose-based source classification. Compare chosen, equal (1/3 each), and authority-heavy (0.25,0.50,0.25) while fixing threshold/floors/mapping/input context.

- Secondary: scores 0.85 / 0.8333333333333333 / 0.75; pass / pass / human_review.
- Official indirect: 0.925 / 0.9166666666666666 / 0.875; all pass.
- Primary: 1 / 1 / 1; all pass.

Ranks remain secondary 3, indirect 2, primary 1 in each run; exactly one routing change. Fixed support/timing explain the one-axis/no-reversal limitation. Exact ties share competition rank, lexical IDs order tied display, null scores are unranked. No expert panel, real judgments or calibration evidence is manufactured.

## Running and verifying

Python >=3.11 declared; Python 3.11.15/Linux tested. Standard library only; no installation, build backend, model, network or credentials. From `src/task-6_saijaz/`:

- `python3.11 -B -m unittest discover -s tests -q` — current suite: 96 tests, including stale-news/status-uncertainty precedence.
- `python3.11 -B -m g2 evaluate --output examples/my-starter-report.json`.
- `python3.11 -B -m g2 compare --output examples/my-sensitivity-report.json`.

Use new destination names; existing files and input aliases are protected. Exit codes describe execution, not routing. Both actual saved examples reproduce byte-for-byte. Original fixture matches HEAD and baseline hash. Tests cover every original case, malformed inputs/weights, unknown/zero-weight blocking, combined priorities, temporal boundaries, constructors, ties, safe errors and application-level offline/clock guards.

See `README.md`, `CLI_USAGE.md`, `ACCEPTANCE.md` and `STAGE_10_RESULTS.md` for exact instructions, traceability and verification limitations. Task text's stale challenge-starter path is documented; actual root fixture is used.

## Trade-offs and limitations

A small dependency-free dataclass/rule implementation provides inspectability, runtime validation and offline reproducibility without unused service interfaces. Source text is inert; expected labels are test-only; IDs never determine policy. Reports expose dates, bases, calibration/version/preferences and all reasons.

Trusted fictional metadata is not independent real-world verification, legal judgment or publication approval. The schema does not represent partial support/qualified scope or optional workflow policies. No other Python version/platform, hidden tests, OS-level network isolation, large-input resource quotas, atomic rollback or adversarial concurrent path mutation is certified. A mid-write error can leave a new partial file. Stage 12 records a historical 95-test rehearsal and the **2026-10-27 corrected-snapshot rehearsal: 96 tests passed in an isolated copy**, all 24 Python files parsed, and default/explicit starter and comparison reports matched saved references byte-for-byte. The original fixture matched HEAD and repository status was unchanged by that rehearsal. See `STAGE_12_RESULTS.md` for method and scope.
