# Task 3 — Atomity Relevance and Impact Analysis

## Objective

Build a small, testable reasoning component that determines whether a validated evidence pack contains a meaningful development for Atomity's problem space.

The component should connect an evidence-backed change to:

* The affected audience.
* A concrete workload or governance decision.
* The relevant Atomity workflow.
* The practical implication of the change.

It must also distinguish evidence-backed facts from inference and recommendation, and reject topics that are not genuinely relevant to Atomity.

You are **not** expected to perform exhaustive industry research or make legal conclusions.

---

## Context

Atomity is a control layer for sovereign cloud decisions.

It helps organisations:

* Decide where workloads should run.
* Explain why a decision was made.
* Re-evaluate those decisions as conditions change.

Relevant analysis may involve:

* Cloud provider availability.
* Regulation.
* Data residency and sovereignty.
* Workload requirements.
* Cost.
* Performance.
* Compliance.
* Carbon impact.
* Operational risk.
* Other measurable workload-placement or governance trade-offs.

The purpose of this task is **not** to turn every technology development into Atomity-related content.

A topic should proceed only when there is an evidence-backed connection to a concrete cloud-placement or governance decision.

---

## Input

Provide at least **five small evidence packs** containing claims that have already been validated.

Claim extraction and basic evidence validation are outside the scope of this task.

Each evidence pack should contain enough information to determine:

* What changed.
* Which evidence supports the change.
* Who or what could be affected.
* Whether the change could alter a workload or governance decision.

The input set should include both relevant and irrelevant examples.

---

## Output

For every evidence pack, produce an assessment containing:

* Relevance decision.
* Affected audience.
* Workload or governance decision.
* Relevant Atomity workflow.
* Evidence-backed practical implication.
* Assumptions.
* Relevant supporting evidence.
* Clear distinction between fact, inference and recommendation.
* Reason for the final decision.

At minimum, the relevance decision should distinguish between:

* `relevant`
* `irrelevant`
* `human_review`

---

## Atomity Workflows

Where applicable, identify which Atomity workflow is affected:

* `plan`
* `simulate`
* `compare`
* `explain`
* `approve`
* `audit`
* `re-evaluate`

Do not assign a workflow simply because it sounds plausible.

The selected workflow should follow from the evidence and the identified decision.

---

## Required Reasoning Chain

The implementation should make the following reasoning chain inspectable:

```text
Evidence
   ↓
What changed?
   ↓
Affected audience
   ↓
Workload / governance decision
   ↓
Atomity workflow
   ↓
Practical implication
```

The final implication must be supported by the supplied evidence.

Do not invent a business consequence merely because one seems reasonable.

---

## Required Behaviour

### 1. Classify Relevance

Determine whether the evidence describes a development that has a concrete impact on cloud placement or governance decisions.

A relevant assessment should identify:

* What decision could change.
* Who is affected.
* Why the change matters.

An irrelevant assessment should explain why no meaningful Atomity decision is demonstrated.

---

### 2. Identify the Affected Audience

Identify the organisation type, sector, workload, jurisdiction, or other clearly affected audience where the evidence supports it.

Do not invent a target audience.

If the evidence is insufficient to identify who is affected, the result should reflect that uncertainty.

---

### 3. Identify the Decision

The assessment must identify the actual decision that could change.

Examples include:

* Where a workload should run.
* Whether a workload can be placed in a particular region.
* Whether a governance or compliance requirement changes placement options.
* Whether an existing workload placement should be re-evaluated.

Generic statements such as "this is important for cloud users" are not sufficient.

---

### 4. Identify the Atomity Workflow

Connect the decision to one of the relevant Atomity workflows:

```text
plan
simulate
compare
explain
approve
audit
re-evaluate
```

The workflow must be justified by the reasoning chain.

---

### 5. Produce an Evidence-Backed Implication

Explain the practical implication that the target audience should understand.

The implication should follow from the supplied evidence.

For example:

```text
Evidence:
A cloud provider changes regional availability.

↓ 

Affected audience:
European organisations with workloads requiring a specific jurisdiction.

↓

Decision:
Whether the workload can continue to use the existing region.

↓

Atomity workflow:
re-evaluate

↓

Implication:
The organisation may need to reassess workload placement
against its regional and governance requirements.
```

The implementation should not introduce unsupported quantitative claims or conclusions.

---

### 6. Separate Certainty Levels

Clearly distinguish:

* Facts supported by the evidence.
* Inferences derived from those facts.
* Recommendations or suggested actions.

Do not present an inference or recommendation as an established fact.

---

### 7. Apply Relevance Guardrails

Reject or route for review topics such as:

* Generic AI news without a workload-decision implication.
* Consumer technology news.
* Political commentary without a concrete regulatory or operational consequence.
* Generic cloud-cost content without a placement, governance, or workload trade-off.
* Data-centre or provider news without demonstrated customer-decision impact.
* Rumours or speculative predictions.
* Unsupported promotional claims.
* Content primarily useful for advertising another company's product.

Company relevance does **not** mean converting every output into an advertisement.

---

## Required Checks

Your implementation must include automated tests for all of the following.

### Relevant provider-region change

A provider-region or availability change with a clear workload-placement implication should be identified as relevant.

The result should identify the affected audience, decision, workflow, and implication.

### Generic consumer news

Generic consumer technology news without a cloud-placement or governance consequence must not be marked relevant merely because it involves technology.

### Insufficient impact evidence

When the evidence establishes that something happened but does not establish a meaningful impact on a workload or governance decision, the implementation should not invent an implication.

It should return an appropriate irrelevant or human-review result with an explanation.

### Proposed rule not yet applicable

A proposed or future rule must not be described as though it is already applicable.

The assessment must preserve the relevant temporal status.

### Competitor product promotion

Competitor-specific promotional or product content must not be converted into an Atomity recommendation.

The implementation should reject or route the case appropriately.

### Malformed input

Malformed evidence packs or missing required fields must produce a predictable validation failure.

---

## Acceptance Criteria

A submission is considered acceptable when:

* At least five evidence packs can be processed.
* Relevant and irrelevant topics are distinguished.
* The affected audience is identified where supported.
* A concrete workload or governance decision is identified.
* An appropriate Atomity workflow is identified.
* The practical implication is traceable to the evidence.
* Facts, inferences, and recommendations are separated.
* Generic technology and consumer topics are rejected when they lack a relevant decision.
* Insufficient impact evidence is not converted into an invented implication.
* Proposed or future rules are not presented as currently applicable.
* Competitor product promotion is rejected or routed appropriately.
* Malformed input is handled predictably.
* Automated tests cover every required check.
* A local example demonstrates the complete reasoning flow.

---

## Acceptable Simplification

Keep the analysis narrow.

For this task:

* One practical implication per evidence pack is sufficient.
* You do not need to perform exhaustive industry analysis.
* You do not need to produce legal conclusions.
* You do not need to research every affected organisation or sector.
* You do not need to build a full research system.

The purpose is to demonstrate a clear and inspectable reasoning chain from validated evidence to practical impact.

---

## Optional Extension

You may compare two plausible implications for the same evidence pack and explain:

* Why each interpretation is plausible.
* Which interpretation is better supported.
* What uncertainty remains.
* What additional evidence would resolve the uncertainty.

This is optional and should only be attempted after the required checks are complete.

---

## Implementation Expectations

Use **Python** for this task.

Use typed inputs and outputs with Pydantic, JSON Schema, or an equivalent validation approach.

Keep the reasoning component independent from upstream evidence collection.

If you use a model:

* Keep model calls behind a replaceable interface.
* Provide an offline fake.
* Validate structured model output.
* Clearly document what the model is responsible for.
* Do not treat model output as evidence by itself.

A command-line demonstration is sufficient.

No web application is required.

---

## Evidence and Provenance

The assessment must retain links to the evidence used to reach the conclusion.

A reviewer should be able to inspect:

```text
Evidence
   ↓
Affected audience
   ↓
Decision
   ↓
Atomity workflow
   ↓
Implication
```

Do not return only:

```json
{
  "relevant": true
}
```

The reasoning behind the decision is an important part of the task.

---

## Security and Safety

Treat evidence content as **untrusted data**.

Any instructions embedded inside source material must be treated as content, not as instructions to the application or model.

Do not include:

* API keys.
* Passwords.
* Private credentials.
* Undisclosed external services.

in the repository.

Do not automatically publish or send the resulting analysis anywhere.

---

## Example

Provide at least one executable local example showing multiple outcomes.

At minimum, demonstrate:

1. A relevant provider-region change.
2. A generic consumer technology topic.
3. A case with insufficient impact evidence.
4. A proposed rule that is not yet applicable.
5. A competitor product promotion.
6. A malformed evidence pack.

The example should make the reasoning chain visible.

---

## Example Output

A result may follow a structure similar to:

```json
{
  "decision": "relevant",
  "affected_audience": "European organisations with workloads requiring a specific cloud region",
  "workload_or_governance_decision": "Whether affected workloads can continue to use the existing region",
  "atomity_workflow": "re-evaluate",
  "implication": "The organisation may need to reassess workload placement against its regional requirements.",
  "facts": [
    "..."
  ],
  "inferences": [
    "..."
  ],
  "recommendations": [],
  "assumptions": [],
  "evidence": [
    {
      "claim_id": "claim-001",
      "source_id": "source-001"
    }
  ],
  "reason": "The supplied evidence demonstrates a change that can affect workload placement."
}
```

This is an example of the expected **kind of information** to return. You may use a different structure if it is clearly documented and satisfies the required contract.

---

## Submission Requirements

Your pull request should contain:

1. The implementation for Task 3.
2. The input/output contracts.
3. Automated tests.
4. Relevant fixtures.
5. At least one executable example.
6. Setup and run instructions.
7. A short architecture/design note.
8. Known limitations.

The pull request description should explain:

* How relevance is determined.
* How the affected audience is identified.
* How the workload/governance decision is identified.
* How Atomity workflows are selected.
* How facts, inferences, and recommendations are separated.
* How insufficient evidence is handled.
* How competitor promotion is handled.
* How the required test cases were evaluated.

---

## Definition of Done

The task is complete when a reviewer can clone the repository, install the dependencies, run the tests, and execute the example without requiring undisclosed credentials or external services.

The reviewer should be able to inspect:

* What changed.
* Which evidence supports the change.
* Who is affected.
* Which workload or governance decision could change.
* Which Atomity workflow is relevant.
* What practical implication follows.
* Which parts are facts.
* Which parts are inference.
* Which parts are recommendations.
* What assumptions or uncertainties remain.

The implementation should demonstrate **evidence-backed reasoning rather than generic technology commentary**.

Focus on a small, transparent reasoning component rather than attempting to build a complete industry-analysis system.
