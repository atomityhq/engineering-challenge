# Task 6 - G2 Evidence and Current-Validity Gate

**Selected task:** Task 6, "One Content-Quality Gate" (G2).
**Scope:** evidence support, source authority and current validity only. No design, style or engagement scoring.

## What it does, in one minute

For each content case the gate asks four questions in a fixed order:

1. **Hard checks** - is the claim supported, not superseded, not competitor promotion, not in conflict? A failed hard check can never be bought back by a good score.
2. **Freshness** - is the evidence still valid *today* (the fixture's `as_of` date, never the system clock)? News is judged by event date. Rules are judged by status and effective date.
3. **Score** - three criteria (evidence support, source authority, temporal validity) combined with documented weights. Unknown stays unknown.
4. **Decision** - `reject` > `revise` > `human_review` > `pass`, each with named reason codes.

`pass` only means "eligible for the next internal stage under the demo policy". It is not publication approval and not a calibrated quality claim.

## Run it

Needs Python 3.10+ (tested on 3.13). Run from inside this folder, inside a clone of the challenge repo:

```bash
pip install -r requirements.txt
python -m pytest                 # 61 tests
python -m g2_gate all            # evaluate + weight sensitivity + triage queue
python -m g2_gate evaluate       # one report per case (supplied fixture)
python -m g2_gate sensitivity    # weight comparison
python -m g2_gate triage         # work queue with next actions
```

Outputs are written to `examples/` (override with `--out`). The supplied `fixtures/g2-cases.json` is read in place and never copied or changed. No network, credentials or model calls are used.

Note: the task brief names `challenge-starter/g2-cases.json`; in the repository the file is `fixtures/g2-cases.json`, so that is the path used.

## Layout

```
config/g2_policy.json     weights, rationale, threshold, anchors, next-action wording
g2_gate/models.py         typed input and output contracts (Pydantic)
g2_gate/config.py         policy loading; weights validated (>= 0, sum to 1)
g2_gate/loader.py         fixture validation; strips test-only expected_decision
g2_gate/checks.py         hard checks
g2_gate/freshness.py      freshness and current validity
g2_gate/scoring.py        criterion scores and weighted sum
g2_gate/decision.py       decision precedence
g2_gate/evaluator.py      runs one case end to end
g2_gate/sensitivity.py    weight comparison
g2_gate/triage.py         optional business add-on (work queue)
fixtures/                 3+ extra eligible cases for the sensitivity comparison
tests/                    61 tests
examples/                 generated reports, sensitivity table, triage queue
```

## Design decisions

**Hard checks before scoring.** The four hard checks run first. If any fails, no weighted score is computed at all, so a high score cannot hide a failure (tested by `test_failed_hard_check_cannot_pass_even_with_a_high_score` and `test_hard_failure_gets_no_score_in_a_real_case`).

**Freshness is separate from the score.** Each report has its own `freshness` block: which date type was used, the date, the age, whether the rule applies now, and a plain-English reason.

- News: judged by `event_date` against the fixture's 30-day demo window. A new article about an old event is stale (`recent-article-old-event`, 643 days).
- Regulation: judged by `current_status` and `effective_from`. An old but in-force rule is current (`old-law-current`).
- Future rule: scores as valid but is labelled `not_yet_applicable` and carries the note `RULE_NOT_YET_APPLICABLE`. It is never described as applicable now (`future-rule`).
- Impossible or contradictory dates (an event after `as_of`; "current" but effective in the future) go to `human_review` as `INCONSISTENT_METADATA`.
- The 30-day window is the fixture's test convention, not a validated threshold. The report says so.

**Unknown never becomes zero.** A missing event date, effective date, verification date, support flag, content type or unrecognised source type leaves that criterion `null`, the score `null`, and routes to `human_review` with the reason visible.

**Decision precedence** (the more final or fixable the problem, the earlier it wins):

| Tier | Meaning | Reason codes |
|---|---|---|
| reject | prohibited, not fixable | `COMPETITOR_PROMOTION` |
| revise | known, repairable | `UNSUPPORTED_CLAIM`, `SUPERSEDED_EVIDENCE`, `STALE_EVENT` |
| human_review | cannot tell | all `UNKNOWN_*`, `CONFLICTING_EVIDENCE`, `INCONSISTENT_METADATA`, `CRITERION_BELOW_FLOOR`, `BELOW_THRESHOLD` |
| pass | everything proven | `ALL_HARD_CHECKS_PASSED`, `ALL_CRITERIA_KNOWN`, `THRESHOLD_MET` |

When several tiers apply, the highest wins and lower findings stay visible in `additional_findings` (for example a stale case that is also conflicting is `revise`, with the conflict still listed). Fail-safe: if nothing is wrong but a pass cannot be proven, the result is `human_review` / `INCOMPLETE_EVALUATION`, never a silent pass.

**No cheating by id or text.** The evaluator reads only structured metadata. It never reads the case id or the statement, and `expected_decision` is removed by the loader before evaluation. Tests cover a renamed case and an instruction hidden in a statement.

## Criterion anchors

| Criterion | 0 | 0.5 | 1 |
|---|---|---|---|
| Evidence support | not supported | partial/qualified support (defined; starter metadata is true/false so it is not produced) | directly supported |
| Source authority | competitor | secondary (useful but indirect) | primary authority |
| Temporal validity | superseded, or news older than the window | looks valid but last verified more than 90 days before `as_of` | within window / rule status clear and recently verified |

Contradiction is only a hard check, not also part of evidence support, so the same problem is not penalised twice.

## Weights, rationale and threshold (provisional, uncalibrated)

| Criterion | Weight | Why |
|---|---|---|
| Evidence support | 0.5 | An unbacked claim is the most damaging mistake for buyers who check sources. |
| Temporal validity | 0.3 | A true statement about a rule that no longer applies still misleads a placement decision. |
| Source authority | 0.2 | Starter metadata only has coarse source labels, and competitor promotion is already a hard check. |

`score = 0.5 * evidence + 0.3 * temporal + 0.2 * authority`.

Config rules (enforced when the policy loads): every weight >= 0, and the weights must sum to 1 within a tolerance of `1e-9` (`WEIGHT_TOLERANCE` in `g2_gate/config.py`). The tolerance only absorbs floating-point rounding (for example 1/3 + 1/3 + 1/3); a real error such as 1.000001 is rejected.

**Pass threshold 0.8 and criterion floor 0.5.** One weak spot is tolerated (secondary source: 0.90; primary rule last verified long ago: 0.85). Two at once are not (secondary source also verified long ago: 0.75, goes to a person). A criterion below 0.5 blocks a pass even if the average is high.

**Calibration status:** `uncalibrated`. No human judgement data exists, so none of these numbers is claimed to be validated. The score is an index, not a probability, and every report says so.

## Weight sensitivity

See `examples/weight-sensitivity.md`. Eight eligible cases are compared under three weight sets: chosen, equal, and `authority_first` (0.35/0.2/0.45).

- Scores move for 4 cases and ranks move for 4 cases.
- Routing changes for one case: `extra-secondary-news-recent` passes under the chosen and equal weights but goes to `human_review` when authority is weighted heavily.
- Routing is unchanged for the other 7.
- Limitation: the nine supplied starter cases barely exercise the weights (most score 1.0 or have no score), so the four extra cases in `fixtures/extra-eligible-cases.json` were written to vary authority and verification age. They are synthetic and made to produce differences; they do not show the weights are right.

## Business add-on: triage queue

`python -m g2_gate triage` turns decisions into a work queue (`examples/triage-queue.md`): ready, fix and resubmit, needs a person, do not publish. Each non-pass case gets a concrete next action keyed to its reason code.

Why it is worth having: Atomity sells auditable decision records to regulated buyers. The gate already produces reason-coded decisions; the triage queue shows how those become team workload, so reviewers spend time on real judgement calls rather than working out why something stopped. It is a separate module that only reads finished reports, and the action wording lives in the config file so a content team can edit it without touching code.

## How each acceptance requirement is met

| Requirement | Where |
|---|---|
| Load fixture, fixed `as_of`, validate envelope and fields | `loader.py`, `models.py`, `test_config_and_fixture.py` |
| No branching on case id or statement text | `evaluator.py`; `test_decision_ignores_*` |
| Hard checks before scoring; failure cannot be overridden | `checks.py`, `evaluator.py`; `test_decision_rules.py` |
| Freshness separate and explained; no universal age penalty | `freshness.py`; `test_starter_cases.py` |
| Three criteria with 0 / 0.5 / 1 anchors | `config/g2_policy.json`, this README |
| Weighted sum; weights >= 0 and sum to 1 | `config.py`; `test_negative_weight_rejected`, `test_weights_must_sum_to_one` |
| Weight rationale, provisional status | `config/g2_policy.json` (loader refuses a weight without a rationale) |
| Unknown is null, not zero | `scoring.py`; `test_unknown_criterion_is_null_and_goes_to_a_person` |
| Decision precedence | `decision.py`; `test_precedence_*` |
| All 9 starter cases processed | `test_all_supplied_cases_are_processed` |
| Missing required field fails predictably | `test_missing_required_case_field_is_a_predictable_error` |
| 3+ extra eligible cases; 3 weight configs | `fixtures/extra-eligible-cases.json`; `test_reports_and_cli.py` |
| Score is not a probability | `score_note` in every report |

## Assumptions (mine, not from the brief)

- The fixture only contains `primary_authority` and `competitor` source types. I added `secondary` = 0.5 so the extra cases can vary authority. Any other source type is treated as unknown, not zero.
- A 90-day re-verification window (`verification_max_age_days`) is my own choice. It only gives temporal validity 0.5; it never fails a case on its own.
- If `supported` is true/false the 0.5 evidence level is never produced.

## Known limitations

- Fixture metadata (`supported`, `superseded`, `contradiction`) is trusted as supplied. The gate routes and scores those assertions; it does not verify real-world truth.
- Weights, threshold, floor and the 90-day window are provisional and uncalibrated.
- Only the 30-day news window comes from the fixture's demo policy, and it is a test convention.
- Evidence support is binary because the input is binary.
- Rank ties share the same rank.
- Not built: parsing real documents, live sources, or any model-assisted step. The gate is deterministic rules only.

## Security

Statements and source text are treated as data. They are never executed, never used for decisions, and unknown fields in a fixture are rejected rather than ignored. No secrets or external services.
