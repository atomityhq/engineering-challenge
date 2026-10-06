# Evidence-to-Insight Engineering Challenge

This repository contains the materials for the **Evidence-to-Insight Engineering Challenge**.

The challenge is designed to evaluate practical engineering judgment across evidence handling, validation, reasoning, content generation, visual rendering, and auditability.

## Repository Structure

```text
engineering-challenge/
├── README.md
├── CODE_OF_CONDUCT.md
│
├── challenge/
│   ├── challenge.md
│   └── tasks/
│       ├── task-1.md
│       ├── task-2.md
│       ├── task-3.md
│       ├── task-4.md
│       ├── task-5.md
│       ├── task-6.md
│       ├── task-7.md
│       └── task-8.md
│
├── design/
│   ├── atomity.css
│   ├── atomity_logo.svg
│   └── fonts/
│       ├── GoogleSansCode-VariableFont_MONO,wght.ttf
│       ├── GoogleSansFlex-VariableFont_GRAD,ROND,opsz,slnt,wdth,wght.ttf
│       ├── GowunBatang-Bold.ttf
│       └── GowunBatang-Regular.ttf
│
├── fixtures/
│   └── g2-cases.json
│
└── src/
```

### `challenge/`

Contains the challenge brief and the individual task specifications.

Start with:

* [`challenge/challenge.md`](challenge/challenge.md)
* [`challenge/tasks/`](challenge/tasks/)

### `design/`

Contains the visual/design assets provided for the challenge:

* [`design/atomity.css`](design/atomity.css): stylesheet with the design tokens and styles to use for any rendered output
* [`design/atomity_logo.svg`](design/atomity_logo.svg): logo asset
* [`design/fonts/`](design/fonts/): the font files used by the design

For the wider Atomity design system, including components and usage guidance, see the Atomity Storybook: [github.com/atomityhq/storybook](https://github.com/atomityhq/storybook).

### `fixtures/`

Contains supplied input data for the challenge.

The repository currently includes the synthetic G2 dataset used by **Task 6**:

```text
fixtures/g2-cases.json
```

For other tasks, candidates should create the small synthetic or local fixtures required by their selected task, inside their own submission folder (see [`src/`](#src)).

### `src/`

Candidate submissions.

Each submission lives in its own folder directly under `src/`, named in the format:

```text
{task}_{name}
```

* `{task}`: the selected task, written as in its file name (`task-1` to `task-8`).
* `{name}`: the candidate's name or GitHub username, in lowercase, with words separated by hyphens.

For example, a submission for Task 6 by Jane Doe goes in `src/task-6_jane-doe/`.

All files for the submission go inside that folder, including:

* the implementation;
* the fixtures the candidate created;
* automated tests demonstrating correctness, acceptance criteria, and relevant failure cases;
* an executable example or demonstration output; and
* a `README.md` with setup, run, and test instructions and the design note.

For example:

```text
src/
└── task-6_jane-doe/
    ├── README.md
    ├── ...           # implementation
    ├── fixtures/
    ├── examples/
    └── tests/
```

The supplied files in `fixtures/` should be read from their existing location, not copied or modified. A submission should not change any files outside its own folder.

## How the Challenge Works

Choose **one task** from Tasks 1–8 and implement the required component.

Each task is intentionally scoped as a small, testable engineering problem. You do not need to build the entire Evidence-to-Insight system.

Your implementation should:

* follow the contract defined by the selected task;
* use typed inputs and outputs;
* include appropriate local fixtures;
* include automated tests;
* provide an executable example;
* handle relevant failure cases;
* document important architectural decisions; and
* remain runnable without undisclosed credentials or external services.

The task specification is the source of truth for the requirements and acceptance checks for that task.

## Running the Project

The repository does not ship a dependency file. Candidates should include whatever their implementation needs to install its dependencies, and document the exact commands for setting up, running, and testing their selected task.

## Candidate Submission

A complete submission should make it easy to understand and verify:

1. **What task was selected**
2. **How the implementation works**
3. **How to run it**
4. **How the tests are run**
5. **What fixtures and assumptions were used**
6. **How the acceptance criteria are satisfied**
7. **What important engineering trade-offs were made**

Keep the implementation focused on the selected task. Additional features are not expected and do not compensate for missing acceptance criteria.

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

See the individual task specification for task-specific requirements and constraints.

## Code of Conduct

Please read the [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.
