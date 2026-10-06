# Task 2 — Claim-to-Evidence Validation

## Objective

Build a small, testable component that determines whether factual claims are adequately supported by the supplied evidence.

The component should connect each claim to its supporting source evidence, identify contradictions, distinguish facts from inferences, and make uncertainty visible.

You are **not** required to build a claim-extraction system. The claims and source excerpts are provided as input.

---

## Input

Provide at least **five pre-extracted claims** together with their source excerpts.

Each claim should reference one or more supplied sources.

The input should contain enough variation to demonstrate:

* A directly supported claim.
* An unsupported numerical claim.
* A claim referencing a missing source.
* Conflicting source excerpts.
* An inference incorrectly presented as a fact.
* At least one malformed input.

Claim extraction itself is **out of scope**.

---

## Output

For every claim, produce a validation result containing:

* Claim identifier.
* Claim text.
* Support status.
* Supporting source IDs.
* Exact evidence locator.
* Fact/inference classification.
* Contradictions, where applicable.
* Unresolved questions, where applicable.
* A brief explanation for the decision.

The output should make it possible for a reviewer to understand **why the claim was considered supported, unsupported, or uncertain**.

---

## Support Status

At minimum, distinguish between:

* `supported`
* `unsupported`
* `uncertain`

Do not force a binary decision when the supplied evidence is contradictory or insufficient.

---

## Required Behaviour

### 1. Resolve References

For each claim, verify that its referenced sources exist.

Detect:

* Missing source IDs.
* Invalid source references.
* Invalid or missing evidence locators.
* Malformed claim records.

A missing source must not be silently ignored.

---

### 2. Compare Claim Against Evidence

Determine whether the supplied evidence actually supports the claim.

The implementation should distinguish between:

**Supported**

The evidence directly supports the claim.

**Unsupported**

The evidence does not provide adequate support for the claim.

**Uncertain**

The available evidence is ambiguous, incomplete, or contradictory.

The decision should include a short explanation.

---

### 3. Preserve Conflicting Evidence

When two or more supplied sources disagree, do not simply choose the source that produces the preferred answer.

The disagreement must remain visible in the result.

For example:

```text
status: uncertain

contradictions:
  - source_a says X
  - source_b says Y

reason:
  The supplied evidence contains unresolved disagreement.
```

The component is responsible for identifying and preserving the conflict, not inventing a resolution.

---

### 4. Classify Claims

Classify claims as appropriate:

* `fact`
* `inference`

The classification should reflect what the supplied evidence supports.

An inference must not automatically be treated as a factual statement merely because it is plausible.

For example:

> "The regulation was published on 1 June."

may be a fact if directly supported by the evidence.

Whereas:

> "This will significantly increase cloud migration costs."

may be an inference unless the supplied evidence directly establishes that conclusion.

---

### 5. Explain the Decision

Every validation result should contain a concise reason.

The explanation should identify the evidence behind the decision rather than simply returning a score.

For example:

```text
status: unsupported

reason:
  The claim states that costs increased by 30%, but the supplied
  source excerpt contains no numerical evidence supporting that figure.
```

---

## Required Checks

Your implementation must include automated tests for all of the following.

### Direct support

A claim that is directly supported by the supplied evidence should be marked as supported.

The output must identify the supporting source and evidence locator.

### Unsupported numerical claim

A numerical claim without supporting evidence must be flagged as unsupported.

Do not infer or estimate the missing number.

### Missing source

A claim referencing a source that does not exist in the supplied evidence set must be handled explicitly.

It must not be treated as supported.

### Conflicting excerpts

When supplied excerpts contradict one another, the disagreement must remain visible.

The implementation should not silently select one source.

### Inference incorrectly labelled as fact

A claim that represents an inference must not automatically be accepted as a fact simply because the underlying evidence is related.

The classification and explanation should expose the issue.

### Malformed input

Malformed claims, source references, or evidence locators must result in a predictable validation failure.

---

## Acceptance Criteria

A submission is considered acceptable when:

* The supplied claims can be loaded and validated.
* Source references are resolved correctly.
* Missing sources are detected.
* Evidence locators are validated.
* Claims are classified as supported, unsupported, or uncertain.
* Supporting evidence is preserved with each result.
* Exact evidence locations can be inspected.
* Conflicting evidence remains visible.
* Facts and inferences are distinguished.
* Unsupported numerical claims are rejected.
* Missing or insufficient evidence does not result in a false positive.
* Every decision includes a brief explanation.
* Malformed input is handled predictably.
* Automated tests cover every required check.
* A local example demonstrates the complete validation flow.

---

## Acceptable Simplification

A narrow **rule-based baseline** for a declared claim type is acceptable.

For example, you may implement a deliberately limited validator for a specific structured claim format.

However, do **not** claim that general semantic verification has been solved through simple substring or keyword matching.

If your implementation has limitations, document them clearly.

The objective is to demonstrate sound engineering judgment and honest handling of uncertainty.

---

## Optional Extension

You may compare a model-assisted verifier against your baseline using additional held-out examples.

If you use a model:

* Keep the model call behind a replaceable interface.
* Provide an offline fake for tests and local execution.
* Validate the model's structured output.
* Record the relevant prompt/model configuration.
* Clearly distinguish the fake/offline behaviour from actual model quality.

A model call by itself is not sufficient.

---

## Implementation Expectations

Use **Python** for this task.

Use typed inputs and outputs with Pydantic, JSON Schema, or an equivalent validation approach.

The validator should be structured so that its decision logic can be tested independently from any optional model or external service.

A command-line example is sufficient.

No web application is required.

---

## Evidence and Provenance

Every material claim decision should retain its evidence lineage.

A reviewer should be able to answer:

> "Which source passage caused the system to make this decision?"

Therefore, avoid returning only a final boolean or score.

A useful result should contain:

```text
Claim
  ↓
Source ID
  ↓
Evidence locator / excerpt
  ↓
Validation decision
  ↓
Reason
```

Evidence should remain inspectable after validation.

---

## Security and Safety

Treat source excerpts as **untrusted data**.

Source text may contain embedded instructions or prompt-injection content. Such text must be treated as evidence content, not as instructions to the application or model.

Do not include:

* API keys.
* Passwords.
* Private credentials.
* Undisclosed external services.

in the repository.

---

## Example

Provide at least one executable local example covering multiple outcomes.

The example should demonstrate:

```text
Claim
  ↓
Resolve source references
  ↓
Locate evidence
  ↓
Classify claim
  ↓
Compare against evidence
  ↓
Detect contradictions
  ↓
Produce validation result
```

At minimum, demonstrate:

1. A supported claim.
2. An unsupported numerical claim.
3. A missing source.
4. A conflicting evidence case.
5. An inference/fact classification case.
6. A malformed input case.

---

## Example Output

A result may follow a structure similar to:

```json
{
  "claim_id": "claim-001",
  "status": "supported",
  "classification": "fact",
  "source_ids": ["source-001"],
  "evidence": [
    {
      "source_id": "source-001",
      "locator": "paragraph-3",
      "excerpt": "..."
    }
  ],
  "contradictions": [],
  "unresolved_questions": [],
  "reason": "The supplied source directly supports the stated claim."
}
```

This is an example of the expected **kind of information** to return. You may choose a different structure if it is clearly documented and satisfies the required contract.

---

## Submission Requirements

Your pull request should contain:

1. The implementation for Task 2.
2. The input/output contracts.
3. Automated tests.
4. Relevant fixtures.
5. At least one executable example.
6. Setup and run instructions.
7. A short architecture/design note.
8. Known limitations.

The pull request description should explain:

* How source references are resolved.
* How support is determined.
* How contradictions are handled.
* How facts and inferences are classified.
* How uncertainty is represented.
* What limitations exist in the validation approach.
* How the required test cases were evaluated.

---

## Definition of Done

The task is complete when a reviewer can clone the repository, install the dependencies, run the tests, and execute the example without requiring undisclosed credentials or external services.

The reviewer should be able to inspect:

* The original claim.
* Its referenced sources.
* The exact supporting evidence.
* The validation status.
* The fact/inference classification.
* Any contradiction.
* Any unresolved question.
* The reason for the final decision.

The implementation should prefer **transparent and inspectable validation** over an opaque confidence score.

Focus on a small, reliable validator rather than attempting to solve general-purpose semantic verification.
