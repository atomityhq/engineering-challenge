# G2 weight sensitivity comparison

Policy `g2-prototype-v1` (uncalibrated). Baseline: `provisional-v1`. Threshold 0.8 (provisional) and criterion floors are held constant across configurations.

## Configurations

| Configuration | Status | evidence_support | source_authority | temporal_validity |
| --- | --- | ---: | ---: | ---: |
| `provisional-v1` | provisional | 0.5 | 0.3 | 0.2 |
| `equal-v1` | comparison-only | 0.3333 | 0.3333 | 0.3333 |
| `freshness-weighted-v1` | comparison-only | 0.35 | 0.2 | 0.45 |

## Eligible cases

Each cell: score (rank) decision. ES / SA / TV = evidence support / source authority / temporal validity.

| Case | ES | SA | TV | `provisional-v1` | `equal-v1` | `freshness-weighted-v1` | Rank changed | Routing changed |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| `current-news` | 1 | 1 | 1 | 1.0000 (#1) pass | 1.0000 (#1) pass | 1.0000 (#1) pass | no | no |
| `future-rule` | 1 | 1 | 1 | 1.0000 (#1) pass | 1.0000 (#1) pass | 1.0000 (#1) pass | no | no |
| `old-law-current` | 1 | 1 | 1 | 1.0000 (#1) pass | 1.0000 (#1) pass | 1.0000 (#1) pass | no | no |
| `w-primary-news-verified` | 1 | 1 | 1 | 1.0000 (#1) pass | 1.0000 (#1) pass | 1.0000 (#1) pass | no | no |
| `w-rule-status-unverified` | 1 | 1 | 0.5 | 0.9000 (#5) pass | 0.8333 (#5) pass | 0.7750 (#7) human_review | yes | yes |
| `w-secondary-news` | 1 | 0.5 | 1 | 0.8500 (#6) pass | 0.8333 (#5) pass | 0.9000 (#5) pass | yes | no |
| `w-qualified-rule` | 0.5 | 1 | 1 | 0.7500 (#7) human_review | 0.8333 (#5) pass | 0.8250 (#6) pass | yes | yes |
| `w-secondary-news-unverified` | 1 | 0.5 | 0.5 | 0.7500 (#7) human_review | 0.6667 (#8) human_review | 0.6750 (#9) human_review | yes | no |
| `w-qualified-secondary-future-rule` | 0.5 | 0.5 | 1 | 0.6000 (#9) human_review | 0.6667 (#8) human_review | 0.7250 (#8) human_review | yes | no |

## Ranking per configuration

- `provisional-v1`: current-news = future-rule = old-law-current = w-primary-news-verified > w-rule-status-unverified > w-secondary-news > w-qualified-rule = w-secondary-news-unverified > w-qualified-secondary-future-rule
- `equal-v1`: current-news = future-rule = old-law-current = w-primary-news-verified > w-qualified-rule = w-rule-status-unverified = w-secondary-news > w-qualified-secondary-future-rule = w-secondary-news-unverified
- `freshness-weighted-v1`: current-news = future-rule = old-law-current = w-primary-news-verified > w-secondary-news > w-qualified-rule > w-rule-status-unverified > w-qualified-secondary-future-rule > w-secondary-news-unverified

## Rank position changes (relative to the baseline; competition ranking, ties share a rank)

- `w-rule-status-unverified`: #5 → #7 under `freshness-weighted-v1`
- `w-secondary-news`: #6 → #5 under `equal-v1`, #6 → #5 under `freshness-weighted-v1`
- `w-qualified-rule`: #7 → #5 under `equal-v1`, #7 → #6 under `freshness-weighted-v1`
- `w-secondary-news-unverified`: #7 → #8 under `equal-v1`, #7 → #9 under `freshness-weighted-v1`
- `w-qualified-secondary-future-rule`: #9 → #8 under `equal-v1`, #9 → #8 under `freshness-weighted-v1`

## Pairwise order changes (relative to the baseline)

- under `equal-v1`: w-rule-status-unverified > w-qualified-rule becomes w-qualified-rule = w-rule-status-unverified
- under `equal-v1`: w-secondary-news > w-qualified-rule becomes w-qualified-rule = w-secondary-news
- under `equal-v1`: w-qualified-rule = w-secondary-news-unverified becomes w-qualified-rule > w-secondary-news-unverified
- under `equal-v1`: w-secondary-news-unverified > w-qualified-secondary-future-rule becomes w-qualified-secondary-future-rule = w-secondary-news-unverified
- under `equal-v1`: w-rule-status-unverified > w-secondary-news becomes w-rule-status-unverified = w-secondary-news
- under `freshness-weighted-v1`: w-rule-status-unverified > w-qualified-rule becomes w-qualified-rule > w-rule-status-unverified
- under `freshness-weighted-v1`: w-qualified-rule = w-secondary-news-unverified becomes w-qualified-rule > w-secondary-news-unverified
- under `freshness-weighted-v1`: w-secondary-news-unverified > w-qualified-secondary-future-rule becomes w-qualified-secondary-future-rule > w-secondary-news-unverified
- under `freshness-weighted-v1`: w-rule-status-unverified > w-secondary-news becomes w-secondary-news > w-rule-status-unverified

## Routing changes (relative to the baseline)

- `w-rule-status-unverified`: pass → human_review under `freshness-weighted-v1`
- `w-qualified-rule`: human_review → pass under `equal-v1`, human_review → pass under `freshness-weighted-v1`

## No change under any configuration

- `current-news`
- `future-rule`
- `old-law-current`
- `w-primary-news-verified`

## Not compared (not eligible for scoring)

- `recent-article-old-event` (fixtures/g2-cases.json): revise; freshness status is 'stale'
- `unknown-date` (fixtures/g2-cases.json): human_review; freshness status is 'unknown'; unknown criteria: temporal_validity
- `unsupported-claim` (fixtures/g2-cases.json): revise; hard checks not passed: material_claim_supported
- `superseded-source` (fixtures/g2-cases.json): revise; hard checks not passed: evidence_not_superseded; freshness status is 'superseded'
- `competitor-promotion` (fixtures/g2-cases.json): reject; hard checks not passed: no_competitor_promotion, source_not_competitor
- `conflicting-evidence` (fixtures/g2-cases.json): human_review; hard checks not passed: no_material_contradiction

## Notes and limitations

- Cases whose criteria are all equal score the same under every configuration, because weights sum to 1; weights only matter where criteria differ: current-news, future-rule, old-law-current, w-primary-news-verified.
- evidence_support takes only [0.5, 1.0] among eligible cases: unsupported (0) and unknown support are routed by hard checks before scoring, so the score never sees them.
- The threshold (0.8) and floors are held constant. They were chosen with provisional-v1 in mind, so part of any routing change under another configuration reflects a threshold that was not re-tuned for it.
- Scores are provisional, uncalibrated prototype indices, not probabilities. Rank and routing changes show sensitivity to a preference choice; they do not show which configuration is correct.
