# Additional synthetic sensitivity cases

`additional-cases.json` is submission-owned and does not copy or modify the original starter fixture. All names, events, rules, publishers, and institutions are fictional. Dates use the same explicit assessment date (2026-10-06) and news limit (30 days). No expected labels are included.

| Case | Asserted source relationship | Authority preference | Temporal basis |
| --- | --- | --- | --- |
| secondary-transit-report | Independent reputable secondary publisher reporting an originating announcer's event | 0.5 | Event on October 2; current coverage |
| indirect-institutional-rule | Official institution reporting another issuer's rule, not the issuer itself | 0.75 | Effective March 2020; still current |
| primary-future-rule | Primary issuer describing its own adopted future rule | 1.0 | Effective January 2027; not applicable today |

Relationships and support are trusted metadata assertions, never inferred by parsing statements. The cases vary content/date context but each has support and temporal validity 1. Authority is therefore the only changing score axis. All three are scoring-eligible; the chosen configuration passes them. Authority-heavy weights route secondary reporting to review without changing rank order. This demonstrates policy sensitivity, not independent expert judgment or calibration.

Load the fixture using the existing strict `g2.fixtures.load_fixture` adapter and compare it through `g2.sensitivity.compare_weights`. CLI invocation and saved generated JSON examples remain Stage 9 work.
