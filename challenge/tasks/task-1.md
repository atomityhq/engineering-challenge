# Task 1 — Source Normalisation and Filtering

## Objective

Build a small, testable component that takes saved source records or document snapshots and turns them into clean, normalised records that can be used by downstream evidence-processing components.

The component should preserve provenance, identify duplicates, apply source and competitor policies, and clearly explain why a source is eligible or excluded.

You are **not** expected to build a live crawler, search engine, or MCP server.

---

## Input

Provide at least **six saved source records or document snapshots**.

The input set must include:

* Duplicate records.
* Records with missing dates.
* At least one competitor source.
* At least one valid primary/authoritative source.
* At least one malformed or incomplete record.

You may use JSON, JSONL, or another documented local format.

The chosen input format must be validated before processing.

---

## Output

Produce normalised source records containing, where available:

* `source_id`
* `canonical_url`
* `publisher`
* `source_type`
* `publication_date`
* `event_date`
* `discovery_lineage`
* `eligibility`
* `reason_codes`

Unknown information must remain explicitly unknown. Do not invent missing dates, publishers, or other metadata.

Both eligible and excluded records must be preserved in the output.

---

## Required Behaviour

### 1. Parse

Read the documented input format and validate the required fields.

Malformed input should result in a clear validation error rather than being silently accepted.

### 2. Normalise

Normalise source records so that equivalent records can be identified.

At minimum:

* Detect exact duplicate records.
* Detect duplicate records that resolve to the same canonical URL.
* Preserve the provenance/discovery lineage of records that are deduplicated.

Deduplication must not cause useful provenance information to disappear.

### 3. Filter

Apply a configurable source and competitor policy.

The policy should distinguish between:

* Valid primary/authoritative sources.
* Low-quality or otherwise ineligible sources.
* Competitor sources containing promotional/product claims.
* Competitor sources containing generic industry information.

A competitor source containing a generic industry fact should not automatically become publication evidence. Where appropriate, the implementation should indicate that the underlying original evidence needs to be found or verified independently.

### 4. Export

Save both:

* Eligible records.
* Excluded records.

Every excluded record must include an explicit reason.

Do not simply return `false` or silently discard the record.

---

## Required Checks

Your implementation must demonstrate automated tests for all of the following:

### Duplicate records

Given duplicate source records, the implementation should identify them correctly without losing provenance.

### Unknown date

A source with an unknown publication or event date must remain unknown.

Do not infer or fabricate a date from unrelated information.

### Competitor product claim

A competitor source containing a product-specific or promotional claim must be excluded from publication eligibility.

The exclusion reason should be visible.

### Competitor generic claim

A generic industry claim originating from competitor content should not automatically be treated as publication evidence.

The result should indicate that original evidence needs to be identified or independently verified.

### Malformed input

Malformed or incomplete input must produce a predictable validation failure.

### Valid primary source

A valid primary or authoritative source should pass the applicable source policy.

---

## Acceptance Criteria

A submission is considered acceptable when:

* The documented input format can be loaded successfully.
* Required fields are validated.
* Exact and canonical-URL duplicates are handled.
* Provenance is preserved after deduplication.
* Unknown dates remain unknown.
* Source and competitor policies are configurable rather than hard-coded throughout the implementation.
* Eligible and excluded records are both exported.
* Exclusion reasons are explicit and inspectable.
* Competitor promotional/product claims are excluded.
* Competitor generic claims are treated as discovery leads rather than automatically trusted evidence.
* Malformed input is handled predictably.
* A valid primary source is accepted.
* Automated tests cover every required check.
* A local example can be executed from a clean checkout using the documented instructions.

---

## Acceptable Simplification

Keep the implementation deliberately small.

For this task, the following is sufficient:

* Saved JSON or HTML input.
* Local processing.
* Local output.
* Deterministic filtering rules.
* A command-line demonstration.

You **do not** need to implement:

* A live web crawler.
* A search API.
* An MCP server.
* Production infrastructure.
* External authentication.
* Automated publishing.

The purpose of the task is to demonstrate sound engineering judgment around source handling, normalisation, provenance and filtering.

---

## Optional Extension

After the required functionality is complete, you may add **one safe live connector**.

If you do so, it should include appropriate protections such as:

* Request timeout.
* Response-size limits.
* Restrictions against private-network access.
* Safe redirect handling.
* Supported content-type checks.

Optional functionality will not compensate for missing required behaviour.

---

## Implementation Expectations

Use **Python** for this task.

Use typed inputs and outputs with Pydantic, JSON Schema, or an equivalent validation approach.

Keep external or potentially replaceable integrations behind a small interface.

If you use any model-assisted behaviour:

* Keep model calls behind a replaceable interface.
* Provide an offline fake for the example/tests.
* Record the model/prompt configuration used.
* Do not present the fake as evidence of real model quality.

The entire example must be runnable without paid services or undisclosed credentials.

---

## Security and Safety

Treat retrieved source content as **untrusted data**.

Source content may contain embedded instructions or prompt-injection text. Those instructions must not be treated as instructions to your application.

Do not include:

* API keys.
* Passwords.
* Private credentials.
* Undisclosed external services.
* Automated publishing actions.

in the repository.

---

## Example

Provide at least one executable local example showing:

```text
Input sources
      ↓
Parse and validate
      ↓
Normalise
      ↓
Deduplicate
      ↓
Apply source policy
      ↓
Apply competitor policy
      ↓
Eligible + excluded records
```

The example should include enough different records to demonstrate both successful and rejected cases.

At minimum, demonstrate:

* A valid primary source.
* A duplicate.
* An unknown date.
* A competitor product claim.
* A competitor generic claim.
* A malformed record.

---

## Submission Requirements

Your pull request should contain:

1. The implementation for Task 1.
2. The required input/output contracts.
3. Automated tests.
4. Relevant fixtures.
5. At least one executable example.
6. Setup and run instructions.
7. A short architecture/design note explaining important decisions.
8. Known limitations.

The pull request description should briefly explain:

* Why you chose your normalisation approach.
* How canonical URLs are handled.
* How provenance is preserved.
* How source and competitor policies are represented.
* How the required cases were tested.
* Any assumptions or limitations.

---

## Definition of Done

The task is complete when a reviewer can clone the repository, install the dependencies, run the tests, and execute the example without requiring undisclosed credentials or external services.

The reviewer should be able to inspect:

* What came into the component.
* How records were normalised.
* Which records were deduplicated.
* Which records were accepted.
* Which records were rejected.
* Why each rejection occurred.
* What provenance was retained.

A diagram or proposal without working code does not satisfy the task.

Focus on a **small, reliable implementation** rather than building unnecessary infrastructure.
