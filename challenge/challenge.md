# Evidence-to-Insight Engineering Challenge

## Overview

The **Evidence-to-Insight** system turns saved sources into evidence-backed, reviewable content about developments relevant to Atomity's problem space.

The challenge is designed to evaluate practical engineering judgment across evidence handling, validation, reasoning, content generation, visual rendering, and auditability.

You are **not** asked to build the whole system. You are asked to build **one** small, well-tested component of it.

## The System at a Glance

Each task covers one stage of the overall flow:

```text
Saved Sources
      ↓
Source Normalisation and Filtering ........ Task 1
      ↓
Claim-to-Evidence Validation .............. Task 2
      ↓
Atomity Relevance and Impact Analysis ..... Task 3
      ↓
Evidence-Grounded Writing ................. Task 5
      ↓
Content-Quality Gate (G2) ................. Task 6
      ↓
Resumable Review Workflow ................. Task 4
      ↓
Visual Template ........................... Task 7

Audit Records and Replay (across all stages) .... Task 8
```

Each component should work on its own, using local fixtures in place of the stages around it.

## Tasks

| Task | Title | Focus |
| ---- | ----- | ----- |
| [Task 1](tasks/task-1.md) | Source Normalisation and Filtering | Parse, normalise, deduplicate and filter saved source records while preserving provenance and applying source and competitor policies. |
| [Task 2](tasks/task-2.md) | Claim-to-Evidence Validation | Decide whether pre-extracted claims are supported by the supplied evidence, keep conflicting evidence visible, and separate facts from inferences. |
| [Task 3](tasks/task-3.md) | Atomity Relevance and Impact Analysis | Decide whether a validated evidence pack is genuinely relevant to Atomity, and connect it to an audience, a decision, a workflow and an implication. |
| [Task 4](tasks/task-4.md) | Resumable Review Workflow | Coordinate evaluation, revision and human review, with persisted state so the workflow can resume without repeating completed work. |
| [Task 5](tasks/task-5.md) | Evidence-Grounded Writing | Turn validated evidence into a short professional post in which every material factual statement can be traced to its evidence. |
| [Task 6](tasks/task-6.md) | One Content-Quality Gate | Implement the G2 gate for evidence and current validity, using hard checks and a transparent weighted score, against [`fixtures/g2-cases.json`](../fixtures/g2-cases.json). |
| [Task 7](tasks/task-7.md) | One Visual Template | Build one reusable HTML/CSS template that safely binds approved content, renders it in a browser and validates the result. |
| [Task 8](tasks/task-8.md) | Audit Records and Replay | Record a fixture-driven workflow run so it can be traced, checked for integrity, redacted and replayed deterministically. |

## Choosing a Task

Choose **one task** and implement it end to end.

Pick the task that best shows how you work. Each task is designed to be completed as a small, focused implementation. Depth, correctness and clarity count for more than breadth.

The selected task specification is the **source of truth** for that task's inputs, outputs, required behaviour, required checks and acceptance criteria. Read it in full before starting.

## What Every Submission Should Include

Whatever task you choose, your implementation should:

* follow the contract defined by the selected task;
* use typed inputs and outputs (for example Pydantic, JSON Schema or an equivalent validation approach);
* include appropriate local fixtures;
* include automated tests covering each of the task's required checks;
* provide at least one executable example;
* handle malformed input and the other failure cases named in the task;
* keep replaceable integrations (models, external services) behind small interfaces;
* document important architectural decisions and known limitations; and
* remain runnable without undisclosed credentials or external services.

Use the language and tooling stated in the task specification. Tasks 1–6 require **Python**.

## Design Assets

Tasks that produce visual output (most directly Task 7) should use the design assets in [`design/`](../design/):

* [`design/atomity.css`](../design/atomity.css)
* [`design/atomity_logo.svg`](../design/atomity_logo.svg)
* [`design/fonts/`](../design/fonts/)

For the wider design system, including components and usage guidance, see the Atomity Storybook: [github.com/atomityhq/storybook](https://github.com/atomityhq/storybook).

## Submitting Your Work

Submit your work as a **pull request** to this repository.

Place your entire submission in a single folder under `src/`, named in the format `{task}_{name}`:

* `{task}`: the selected task, written as in its file name (`task-1` to `task-8`).
* `{name}`: your name or GitHub username, in lowercase, with words separated by hyphens.

For example, a Task 6 submission by Jane Doe goes in `src/task-6_jane-doe/`.

Everything for the submission goes inside that folder: the implementation, your fixtures, tests, examples, and a `README.md` with setup, run and test instructions. Read the supplied fixtures from [`fixtures/`](../fixtures/) rather than copying them. Do not change files outside your folder.

Your pull request should make it easy for a reviewer to understand and verify:

1. **Which task was selected**
2. **How the implementation works**
3. **How to install dependencies and run it**
4. **How the tests are run**
5. **What fixtures and assumptions were used**
6. **How each acceptance criterion is satisfied**
7. **What important engineering trade-offs were made**
8. **What the known limitations are**

Each task lists any additional points its pull request description should cover.

## Definition of Done

A submission is complete when a reviewer can:

1. clone the repository;
2. install the dependencies;
3. run the tests; and
4. execute the example,

without undisclosed credentials, paid services or network access to external systems, and can then inspect the inputs, outputs and decisions the component produced.

A diagram or proposal without working code does not satisfy a task.

## What Reviewers Look For

* **Correctness:** the required checks and acceptance criteria are met and tested.
* **Judgment:** the component makes sensible, explainable decisions, especially in edge and failure cases.
* **Traceability:** decisions can be traced back to their inputs and evidence.
* **Clarity:** the code, contracts and documentation are easy to follow.
* **Focus:** the implementation does what the task asks without unnecessary infrastructure.

Additional features are not expected and do not compensate for missing acceptance criteria.

## Important Constraints

The challenge does not require:

* a deployed production service;
* production cloud infrastructure;
* paid model access;
* automated publishing or scheduling;
* external design-tool integration;
* authentication or user-management systems;
* large-scale crawling; or
* implementation of every task.

Local files, SQLite, synthetic data, mock services, and offline model interfaces are acceptable where appropriate.

See the individual task specification for task-specific requirements, acceptable simplifications and optional extensions.
