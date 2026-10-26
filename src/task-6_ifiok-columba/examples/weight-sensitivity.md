# Weight sensitivity

Same cases, three weight sets. Only cases eligible for a score (no failed hard check, no unknown criterion) are compared.

| case | chosen score / rank / decision | equal score / rank / decision | authority_first score / rank / decision | routing changes? |
|---|---|---|---|---|
| current-news | 1.000 / #1 / pass | 1.000 / #1 / pass | 1.000 / #1 / pass | no |
| old-law-current | 1.000 / #1 / pass | 1.000 / #1 / pass | 1.000 / #1 / pass | no |
| recent-article-old-event | 0.700 / #8 / revise | 0.667 / #7 / revise | 0.800 / #6 / revise | no |
| future-rule | 1.000 / #1 / pass | 1.000 / #1 / pass | 1.000 / #1 / pass | no |
| extra-secondary-news-recent | 0.900 / #5 / pass | 0.833 / #5 / pass | 0.775 / #7 / human_review | YES |
| extra-primary-rule-old-check | 0.850 / #6 / pass | 0.833 / #5 / pass | 0.900 / #5 / pass | no |
| extra-secondary-rule-old-check | 0.750 / #7 / human_review | 0.667 / #7 / human_review | 0.675 / #8 / human_review | no |
| extra-primary-news-day-30 | 1.000 / #1 / pass | 1.000 / #1 / pass | 1.000 / #1 / pass | no |

- Eligible cases compared: 8
- Cases whose routing changes with the weights: 1 ['extra-secondary-news-recent']
- Cases whose rank changes with the weights: 4 ['recent-article-old-event', 'extra-secondary-news-recent', 'extra-primary-rule-old-check', 'extra-secondary-rule-old-check']
- Routing unchanged under every weight set: ['current-news', 'old-law-current', 'recent-article-old-event', 'future-rule', 'extra-primary-rule-old-check', 'extra-secondary-rule-old-check', 'extra-primary-news-day-30']

Limitation: cases scoring 1.0 on every criterion score 1.0 under any weights, so they cannot show weight sensitivity. The extra fixtures exist to vary the criteria.
