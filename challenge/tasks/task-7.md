# Task 7 — One Visual Template

## Objective

Build one reusable visual template that converts approved content into a rendered visual.

The component should demonstrate a complete path from:

```text
Approved Content
      ↓
Design Configuration
      ↓
HTML/CSS Template
      ↓
Browser Rendering
      ↓
PNG
      ↓
Visual Validation Report
```

The focus is on **reliable, deterministic rendering of approved content**.

Do not build a complete visual-generation platform.

---

## Input

The task takes:

* Approved text.
* A design configuration.

For the demo, use synthetic approved text.

The design configuration should provide the information required by the supplied design foundation.

---

## Output

Produce:

1. One rendered PNG.
2. One separate visual-validation report.

The primary implementation must use:

```text
HTML + CSS → browser rendering → PNG
```

The output should be generated from the supplied content and design configuration rather than manually edited.

---

# Required Build Steps

## 1. Define Template Slots

The template must define reusable slots for at least:

* Title.
* Body.
* Source note.
* Brand identifier.

A conceptual structure could be:

```text
┌─────────────────────────────────────┐
│ Brand                               │
│                                     │
│ Title                               │
│                                     │
│ Body                                │
│                                     │
│ Source note                         │
└─────────────────────────────────────┘
```

The exact layout is determined by the supplied design foundation described below.

---

## 2. Bind Content Safely

Insert approved content into the template without interpreting the content as HTML.

For example, input such as:

```html
<script>alert("test")</script>
```

must be treated as text.

It must not become executable markup in the rendered output.

Content binding must therefore safely handle:

* HTML-like input.
* Script-like input.
* Special characters.
* Long text.
* Missing fields.

---

## 3. Render the Template

Render the template using a browser-based rendering process.

The implementation must document:

* The rendering command.
* Required dependencies.
* The canvas size.
* Where the rendered output is saved.

The rendering process must be repeatable.

Running the same input and design configuration should produce the same layout and equivalent rendered output.

---

# Canvas Size

For the minimum submission, document and support **one canvas size**.

The broader design foundation supports:

* Single insight image: `1200 × 627`.
* Portrait insight image: `1080 × 1350`.
* Multi-page document: `1080 × 1350` per page.

The minimum Task 7 implementation only needs to implement **one single-slide template**.

---

# 4. Validate the Rendered Result

Generate a separate visual-validation report.

At minimum, validate:

* Required content is present.
* Text does not overflow its intended region.
* Required fields are present.
* Approved text has not been changed.
* Required assets are available.
* The output uses the expected canvas dimensions.

Visual validation must be separate from content-quality scoring.

A visual-quality result must not be combined with the G2 content score from Task 6.

---

# Required Checks

Automated tests must cover the following cases.

## 1. Normal Content

A normal approved content fixture should:

* Render successfully.
* Produce the expected PNG.
* Produce a successful validation report.

---

## 2. Long Title

Provide a fixture containing an unusually long title.

The implementation must detect the resulting layout/overflow problem rather than silently producing an invalid visual.

The validation report should identify the failure.

---

## 3. Long Body

Provide a fixture containing a body that exceeds the available layout space.

The implementation must detect the overflow.

Do not silently clip or hide approved text.

---

## 4. Missing Required Field

Test missing required fields such as:

* Title.
* Body.
* Source note.
* Brand identifier.

The implementation must produce a predictable validation or input error.

---

## 5. HTML/Script-Like Input

Provide content containing HTML or script-like text.

For example:

```html
<script>alert("test")</script>
```

The text must be escaped safely.

The content must not execute.

---

## 6. Changed Approved Text

The approved text must be preserved exactly.

If the renderer or validation process detects that the approved text has been changed, the result must be reported as a failure.

The renderer should not silently rewrite:

* Facts.
* Wording.
* Numbers.
* Source notes.
* Approved claims.

---

# Design Foundation

Use the supplied Atomity design foundation:

```text
design/
├── atomity.css
├── atomity_logo.svg
└── fonts/
```

* [`design/atomity.css`](../../design/atomity.css): the Atomity design system as a single stylesheet with no build step. It defines the font faces, the design tokens as CSS custom properties, base typography and ready-made component styles.
* [`design/atomity_logo.svg`](../../design/atomity_logo.svg): the approved logo.
* [`design/fonts/`](../../design/fonts/): the font files loaded by `atomity.css`.

The Atomity design system, including components and usage guidance, is documented in the Atomity Storybook: [github.com/atomityhq/storybook](https://github.com/atomityhq/storybook). Use it as the visual reference for how the tokens and components should look and be combined.

Link `atomity.css` from the template rather than copying its values. Because `atomity.css` loads its fonts from `./fonts/` relative to itself, reference it in place (or make sure the fonts resolve) so the rendered output uses the real typefaces.

The supplied design foundation is **not** a finished renderer.

The candidate remains responsible for:

* Template implementation.
* Content-to-layout mapping.
* Overflow handling.
* Validation.
* Rendering.

---

# Design Tokens

Use the tokens defined in `atomity.css` rather than hardcoding brand colours, fonts or spacing throughout the template.

Keep these concerns separate:

```text
Content
   ↓
Layout
   ↓
Design Tokens
```

The tokens are CSS custom properties on `:root`, grouped as follows (examples only; see `atomity.css` for the full set):

| Group | Example tokens |
| ----- | -------------- |
| Brand colours | `--atomity-green`, `--atomity-black`, `--atomity-white` |
| Surfaces | `--surface-page`, `--surface-paper`, `--surface-dark` |
| Text | `--text-primary`, `--text-secondary`, `--text-muted`, `--text-on-dark` |
| Borders | `--border-light`, `--border-dark` |
| Typography | `--font-title`, `--font-display`, `--font-body`, `--font-code` |
| Radius | `--radius-sm` … `--radius-2xl`, `--radius-pill` |
| Layout and spacing | `--container-padding`, `--space-section-sm`, `--space-section-md` |
| Shadows | `--shadow-card`, `--shadow-elevated` |

Reference tokens with `var(...)`, for example:

```css
.post-title {
  font-family: var(--font-title);
  color: var(--text-primary);
}
```

Where the template needs a value the stylesheet does not define, such as the canvas size or logo clear space, keep it in the template's own design configuration, derive it from existing tokens where possible, and document it.

---

# Brand Identity

Use only the identity supplied in `design/` and documented in the Storybook.

**Do not invent additional official Atomity brand assets**, such as alternative logos, colours or fonts.

If a required design input is genuinely missing from both, use a clearly labelled neutral value for that input, document the gap, and do not present it as an official Atomity design value.

---

# Reusable Template

The template should be reusable.

Do not generate arbitrary HTML separately for every piece of content.

For example:

```text
Template
   ├── title slot
   ├── body slot
   ├── source slot
   └── brand slot
```

The content should be supplied separately from the template.

This allows the same renderer to process multiple approved content fixtures.

---

# Accessibility

The rendered output should have an accessible HTML representation.

At minimum:

* Use semantic HTML where practical.
* Preserve readable text.
* Use appropriate text hierarchy.
* Avoid relying only on visual decoration to convey information.
* Ensure the HTML representation remains understandable without the final PNG.

---

# Visual Validation Report

Produce a separate report such as:

```json
{
  "template": "single-insight-v1",
  "status": "pass",
  "canvas": {
    "width": 1200,
    "height": 627
  },
  "checks": {
    "required_fields": "pass",
    "overflow": "pass",
    "approved_text_preserved": "pass",
    "assets": "pass"
  },
  "failures": []
}
```

For a failed case:

```json
{
  "template": "single-insight-v1",
  "status": "fail",
  "checks": {
    "required_fields": "pass",
    "overflow": "fail",
    "approved_text_preserved": "pass",
    "assets": "pass"
  },
  "failures": [
    "BODY_OVERFLOW"
  ]
}
```

The exact schema is up to the candidate.

---

# Separation from Content Evaluation

Task 7 must not become another content-quality evaluator.

The responsibilities are separate:

```text
Task 6
Evidence + current validity
        ↓
Approved content
        ↓
Task 7
Visual rendering + visual validation
```

Do not include:

* Evidence-quality scores.
* Writing-quality scores.
* Audience-engagement scores.
* G2 content scores.

inside the visual-validation result.

---

# Security

Treat approved content as untrusted input at the rendering boundary.

The implementation must protect against:

* HTML injection.
* Script execution.
* Unsafe embedded markup.
* Unexpected asset references.

Do not allow content supplied through the input fixture to execute arbitrary browser code.

Do not commit credentials or external service secrets.

---

# Acceptable Simplification

The minimum implementation is:

* One single-slide template.
* One documented canvas size.
* HTML/CSS.
* Browser-based rendering.
* PNG output.
* Automated overflow validation.
* Automated content-preservation validation.
* Basic visual-validation report.

You do **not** need:

* A carousel system.
* Multiple templates.
* Canva integration.
* Generated imagery.
* A full design editor.
* A production cloud rendering service.

---

# External Design Tools

Canva or another external design tool is **not required**.

The primary implementation path should be:

```text
Structured content
      ↓
HTML/CSS
      ↓
Browser
      ↓
PNG or PDF
```

Any optional design-tool import must remain separate from the core renderer.

---

# Developer Handoff

Include or document the design inputs required by the renderer.

Where supplied, these include:

* Logo SVG.
* Licensed fonts or fallback fonts.
* Colour tokens.
* Spacing tokens.
* Typography tokens.
* One example layout.
* Approved sample text.

Reference the supplied assets from the repository's `design/` folder rather than copying or modifying them. Keep any template-specific design configuration inside your submission folder.

Do not create fake official brand assets when they have not been supplied.

---

# Optional Extension

After the primary template is complete, you may add:

* A second slide.
* Multi-page export.
* Additional reusable templates.
* Additional canvas sizes.

These are optional and do not compensate for missing required checks.

---

# Submission Requirements

Submit a pull request containing:

1. The Task 7 implementation.
2. The reusable HTML/CSS template.
3. Design configuration/token integration.
4. Synthetic approved-content fixtures.
5. Automated tests.
6. One successful rendered example.
7. Failure examples.
8. Visual-validation reports.
9. Setup instructions.
10. Rendering instructions.
11. A short decision note describing:

* The chosen template approach.
* One alternative considered.
* Known limitations.
* Integration boundary.

For Task 7, the submission must include the **rendered example**.

---

# Definition of Done

The task is complete when a reviewer can:

1. Install the documented dependencies.
2. Run the documented rendering command.
3. Provide approved synthetic content.
4. Generate the PNG without manually editing it.
5. Inspect the HTML/CSS template.
6. Confirm content is inserted safely.
7. Confirm the approved text is preserved.
8. Confirm the configured canvas size.
9. Run the overflow test.
10. Run the long-title test.
11. Run the long-body test.
12. Run the missing-field test.
13. Run the HTML/script-like input test.
14. Run the changed-text detection test.
15. Inspect the separate visual-validation report.

The final implementation should demonstrate a **small, deterministic, reusable visual rendering component**, not a complete design-generation platform.
