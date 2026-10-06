# Task 6 — One Content-Quality Gate

## Objective

Build one content-quality gate for **G2: evidence and current-validity assessment**.

The component must determine whether a supplied content case is eligible to proceed based on:

* Evidence support.
* Source authority.
* Temporal validity.
* Current applicability.
* Explicit hard checks.
* A transparent weighted score where scoring is possible.

This task is about **evidence and current validity only**.

Do **not** evaluate:

* Design.
* Visual quality.
* Writing style.
* Audience engagement.

Visual quality is a separate concern and must not be included in the G2 score.

---

## Input

Use the supplied synthetic starter cases:

```text
challenge-starter/g2-cases.json
```

All dates and claims in this fixture are **fictional test data**. They are not real regulatory information.

The component should use the fixture's supplied `as_of` value rather than the current system date.

The input must include the stage-specific case data and its supporting evidence/metadata as supplied by the challenge fixture.

---

## Output

Produce one evaluation report per case.

Each report must contain, at minimum:

* Hard-check results.
* Criterion scores.
* Freshness assessment.
* Freshness explanation.
* Weighted score when eligible.
* Decision.
* Reasons.
* Policy/version information.
* Calibration status.

A conceptual output structure is:

```json
{
  "case_id": "unknown-date",
  "gate": "G2",
  "policy_version": "prototype-v1",
  "calibration_status": "uncalibrated",
  "hard_checks": {
    "material_claim_supported": true
  },
  "criteria": {
    "evidence_support": 1.0,
    "source_authority": 1.0,
    "temporal_validity": null
  },
  "freshness": {
    "status": "unknown",
    "reason": "Event date unavailable"
  },
  "weights_version": "provisional-v1",
  "score": null,
  "decision": "human_review",
  "reasons": [
    "UNKNOWN_EVENT_DATE"
  ]
}
```

This is an example of the expected information, not a required exact schema.

---

# Required Evaluation Flow

Implement the evaluation in the following order.

## 1. Load the Fixture

Load:

```text
challenge-starter/g2-cases.json
```

Use the supplied fixed `as_of` date.

Do **not** use today's date to determine freshness.

Validate:

* Fixture envelope.
* Required case fields.
* Case metadata.
* Evidence metadata.
* Criterion inputs.

The evaluator must not branch on individual case IDs or memorise specific statement text.

---

## 2. Perform Hard Checks

Hard checks must be evaluated **before** weighted scoring.

At minimum, check:

* Material claims are supported.
* Evidence is not superseded.
* Competitor product promotion is not permitted to pass.
* Other mandatory evidence/policy constraints supplied by the fixture are satisfied.

A failed hard check cannot be overridden by a high weighted score.

For example:

```text
Hard check failed
       ↓
Do not calculate a passing weighted result
       ↓
Route according to the decision precedence
```

---

## 3. Evaluate Freshness and Current Validity

Freshness must distinguish between:

* Publication date.
* Event date.
* Effective date.
* Current applicability.
* Unknown dates.

A recent article may describe an old event.

An old regulation may still be current and applicable.

A future rule may be correctly described as future without being treated as currently applicable.

Do not use publication age as a universal freshness rule.

---

## Demo Freshness Policy

For the supplied starter cases, use the fixture's demo policy:

> News older than 30 days by event date needs revision.

This is a **test convention**, not a scientifically validated freshness threshold.

The implementation should clearly identify it as such.

A correctly described future rule may pass the freshness check, but it must not be represented as already applicable.

---

## 4. Score the Required Criteria

Use the following core criteria:

### Evidence Support

Does the supplied evidence support the material claim?

### Source Authority

How authoritative is the supplied source for the claim being evaluated?

### Temporal Validity

Is the evidence temporally valid for the claim and `as_of` date?

The exact implementation may use additional subcriteria if justified, but avoid counting the same evidence twice under differently named criteria.

---

# Criterion Anchors

Define observable anchors for each criterion.

At minimum, explain what:

* `0`
* `0.5`
* `1`

mean for each criterion.

For example:

### Evidence Support

| Score | Meaning                                                        |
| ----- | -------------------------------------------------------------- |
| `0`   | Claim is unsupported or contradicted by supplied evidence.     |
| `0.5` | Evidence provides partial or qualified support.                |
| `1`   | Material claim is directly supported by the supplied evidence. |

### Source Authority

| Score | Meaning                                                                    |
| ----- | -------------------------------------------------------------------------- |
| `0`   | Source is inappropriate or provides no meaningful authority for the claim. |
| `0.5` | Source provides some useful authority but is indirect or limited.          |
| `1`   | Source is an appropriate authoritative source for the claim.               |

### Temporal Validity

| Score | Meaning                                                                    |
| ----- | -------------------------------------------------------------------------- |
| `0`   | Evidence is superseded or clearly invalid for the required time period.    |
| `0.5` | Timing is uncertain, partially applicable or requires review.              |
| `1`   | Evidence is temporally appropriate and applicable for the required period. |

These are example anchor structures. The candidate may refine them, but the chosen anchors must be explicit and observable.

---

# Weighted Scoring

For eligible cases, use the transparent weighted-sum model:

```text
score = Σ(weight_i × criterion_i)
```

Each criterion must be between `0` and `1`.

Weights must satisfy:

```text
weight_i >= 0
Σ(weight_i) = 1
```

The score is an interpretable prototype ranking/decision aid.

It is **not proof that content quality is objectively measurable**.

---

## Weight Rationale

Document the decision preference behind every weight.

For example:

* Why should evidence support matter more or less than source authority?
* Why should temporal validity receive its selected weight?
* What failure is the scoring model intended to penalise?

Do not invent unexplained percentages and present them as scientifically established.

---

## Provisional Status

Initial weights and thresholds must be explicitly marked:

```text
provisional
```

or:

```text
uncalibrated
```

unless the implementation has genuine supporting calibration evidence.

Do not claim scientific validation without actual evidence.

---

# Unknown Criteria

If a required criterion is unknown, return a **null score** where the criterion is required for scoring.

Do **not** silently convert:

```text
unknown → 0
```

or:

```text
unknown → default value
```

For example:

```json
{
  "temporal_validity": null,
  "score": null,
  "decision": "human_review"
}
```

The reason for the unknown value must be visible.

---

# Freshness Must Remain Separate

Do not hide freshness inside a generic numerical score.

The report must explain:

* What date was used.
* Which date type it represents.
* Whether the evidence is current.
* Whether applicability is known.
* Whether the date is unknown or conflicting.
* Why the freshness decision was reached.

Do not apply a universal age penalty to every source type.

For example:

> A regulation published several years ago is not automatically stale if it remains applicable.

---

# Score Is Not Probability

A score such as:

```text
0.8
```

must **not** be described as:

```text
80% likely to be correct
```

unless a separate probability calibration procedure has actually been performed.

The weighted score is a prototype quality/index score, not a probability.

---

# Decision Precedence

Apply decisions in this order so outcomes do not overlap.

## 1. Reject

Use `reject` for an explicitly prohibited or non-remediable case.

Examples include:

* Competitor product promotion.
* Out-of-scope content.
* A non-remediable policy violation.
* Exhausted revision limit where applicable.

---

## 2. Revise

Use `revise` for a known and repairable problem.

Examples include:

* Unsupported material claims.
* Superseded evidence.
* Stale event coverage under the demo policy.
* Other identifiable evidence defects that can be corrected.

---

## 3. Human Review

Use `human_review` when:

* Required information is missing.
* A required criterion is unknown.
* Evidence is materially conflicting.
* Calibration is unavailable where required by the selected policy.
* A result falls below the provisional threshold but does not have a known automatic repair.
* An explicit competitor exception requires human judgment.

---

## 4. Pass

Use `pass` only when:

* Mandatory hard checks pass.
* Required criterion floors pass.
* The configured prototype threshold is met.
* Required evidence is available.
* No earlier decision rule applies.

A `pass` means:

> Eligible for the next internal stage under the demo policy.

It does **not** mean publication approval or scientifically calibrated quality.

---

# Starter Cases

The evaluator must process **every supplied starter case**.

The implementation should demonstrate correct routing for cases covering conditions such as:

* Current/recent evidence.
* An old event described by recent reporting.
* An old but currently applicable rule.
* Unknown event date.
* Unsupported claims.
* Superseded evidence.
* Competitor promotion.
* Conflicting evidence.
* Future rules or future applicability.

Do not hard-code expected results by case ID.

The evaluator should derive the result from the case data and the configured rules.

---

# Required Checks

Automated tests must cover all supplied starter cases and additionally verify:

### Invalid weight sum

Reject or fail configuration when:

```text
Σ(weight_i) != 1
```

within the implementation's documented numerical tolerance.

---

### Negative weight

Reject a configuration containing a negative weight.

For example:

```json
{
  "evidence_support": 0.8,
  "source_authority": 0.3,
  "temporal_validity": -0.1
}
```

must not be accepted.

---

### Missing required field

Malformed or incomplete fixture data must produce a predictable validation failure.

---

### Unknown criterion

A required unknown criterion must not silently become zero.

The evaluator should return the appropriate unknown/review behaviour.

---

### Hard failure cannot pass through scoring

A case that fails a mandatory hard check must not pass simply because its weighted score is high.

For example:

```text
hard_check = failed
weighted_score = 0.95
```

must not result in:

```text
decision = pass
```

---

# Weight Sensitivity Comparison

For at least **three eligible cases**, compare:

1. Your chosen weight configuration.
2. Equal weights.
3. A second plausible weight configuration.

Report:

* Scores under each configuration.
* Ranking changes.
* Routing/decision changes.
* Cases where no change occurs.

If there are no ranking or routing changes, explicitly explain the limitation.

This comparison is required to demonstrate that the chosen weighting is not being treated as unquestionable.

---

# Fixture Metadata Boundary

For the supplied starter cases, you may trust metadata assertions such as:

```text
supported
superseded
```

Your component is responsible for routing and scoring those assertions.

It is **not** responsible for verifying the real-world truth of the fictional test data.

Document this boundary clearly.

---

# Example Output

A report could look like:

```json
{
  "case_id": "current-news",
  "gate": "G2",
  "policy_version": "prototype-v1",
  "calibration_status": "uncalibrated",

  "hard_checks": {
    "material_claim_supported": true,
    "evidence_superseded": false,
    "competitor_promotion": false
  },

  "criteria": {
    "evidence_support": 1.0,
    "source_authority": 1.0,
    "temporal_validity": 1.0
  },

  "freshness": {
    "status": "current",
    "event_date": "2026-09-20",
    "reason": "Event falls within the configured demonstration freshness policy."
  },

  "weights_version": "provisional-v1",

  "weights": {
    "evidence_support": 0.5,
    "source_authority": 0.25,
    "temporal_validity": 0.25
  },

  "score": 1.0,

  "decision": "pass",

  "reasons": [
    "All mandatory checks passed.",
    "All required criteria are known.",
    "Prototype threshold was met."
  ]
}
```

The exact numerical values are illustrative only.

Do not copy these example weights without documenting and justifying your own configuration.

---

# Required Test Dataset

In addition to the supplied starter cases, create at least **three additional eligible cases** for the weight-comparison requirement.

These should vary enough to make the comparison meaningful.

Do not make them identical copies of the starter cases.

Keep all fixtures:

* Synthetic.
* Licensed for redistribution.
* Or reduced to the minimum text required for the test.

---

# Implementation Expectations

Use **Python** for this task.

Use typed inputs and outputs with:

* Pydantic.
* JSON Schema.
* Or an equivalent validation mechanism.

A deterministic implementation is sufficient.

You do **not** need an LLM.

You do **not** need learned weights.

A command-line demo is sufficient.

Keep the implementation focused on the G2 gate.

A useful conceptual structure is:

```text
Starter Cases
      ↓
Schema Validation
      ↓
Hard Checks
      ↓
Freshness / Current Validity
      ↓
Criterion Evaluation
      ↓
Weighted Score
      ↓
Decision Policy
      ↓
Evaluation Report
```

---

# Security and Safety

Treat source text as untrusted data.

If a fixture or source contains embedded instructions, those instructions must not alter the evaluator's behaviour.

Do not:

* Execute instructions from source text.
* Include secrets.
* Require undisclosed credentials.
* Publish results externally.
* Use external services when the local implementation can perform the required evaluation.

---

# Acceptable Simplification

The minimum implementation may use:

* Deterministic rules.
* Synthetic fixtures.
* No LLM.
* No learned weights.
* No live external sources.
* Local execution.
* A simple weighted-sum evaluator.

The starter routing expectations are intended to test **implementation consistency**, not scientific validity.

---

# Optional Research Extension

After the primary task is complete, you may obtain independent human judgments and:

* Derive weights from those judgments.
* Evaluate the resulting configuration on held-out topic/event groups.
* Report sample limitations.
* Report reviewer disagreement.
* Compare calibrated and uncalibrated approaches.

This is optional.

Do not manufacture an expert panel or synthetic judgments and present them as real validation.

---

# Submission Requirements

Your pull request should contain:

1. The Task 6 implementation.
2. Typed input/output contracts.
3. G2 policy configuration.
4. Weight configuration.
5. Criterion definitions and anchors.
6. Starter-case fixtures.
7. At least three additional eligible test cases.
8. Automated tests.
9. Weight sensitivity comparison.
10. At least one executable example.
11. Setup and run instructions.
12. A short architecture/design note.
13. Known limitations.

The pull request description should explain:

* The hard checks.
* The freshness policy.
* How current applicability is assessed.
* Criterion definitions.
* Criterion anchors.
* Weight selection.
* Weight rationale.
* Threshold selection.
* Decision precedence.
* Handling of unknown criteria.
* Weight sensitivity results.
* Calibration status.
* The boundary between fixture metadata and real-world verification.

---

# Definition of Done

The task is complete when a reviewer can:

1. Load the supplied `g2-cases.json`.
2. Run the evaluator using the fixture's fixed `as_of`.
3. Validate every starter case.
4. Inspect hard-check results.
5. Inspect freshness and current-validity reasoning.
6. Inspect each criterion score.
7. Inspect the configured weights.
8. Inspect the weighted score where eligible.
9. Inspect the final decision and reasons.
10. Verify that hard failures cannot be overridden by scoring.
11. Verify that unknown criteria do not silently become zero.
12. Verify invalid weight configurations are rejected.
13. Verify at least three eligible cases under three weight configurations.
14. Inspect ranking/routing changes caused by weight changes.
15. Run all automated tests locally without undisclosed credentials.

The implementation should clearly demonstrate that **G2 is an evidence and current-validity gate, not a generic content-quality score**.
