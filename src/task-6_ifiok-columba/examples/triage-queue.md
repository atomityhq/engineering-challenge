# Content triage queue (G2)

13 cases checked: 6 pass, 3 revise, 3 human_review, 1 reject.

Only 'pass' moves on. Everything else has a named next step, so reviewers spend time on real judgment calls instead of working out why something stopped.

## Ready for the next internal stage (6)

- **current-news** - Fictional Authority reports a region availability change.
- **old-law-current** - Fictional Regulation A is still in force and applicable.
- **future-rule** - The fictional rule is adopted and will apply from 2027-01-01, not today.
  - Careful: this rule is not applicable yet. Say "from <date>", not "now".
- **extra-secondary-news-recent** - A fictional trade publication reports a recent provider region change.
- **extra-primary-rule-old-check** - Fictional Regulation B is in force, but its status was last checked months ago.
  - Re-verify the source soon.
- **extra-primary-news-day-30** - Fictional Authority announced a change exactly 30 days before the as_of date.

## Fix and resubmit (3)

- **recent-article-old-event** - A new article describes an old provider event as breaking news.
  - STALE_EVENT: Describe it as past news with its real date, or swap in a recent event. Do not present it as breaking.
- **unsupported-claim** - The draft asserts a 10 percent saving absent from its evidence.
  - UNSUPPORTED_CLAIM: Find a source for the claim or delete the claim. Do not keep unsupported numbers.
- **superseded-source** - An older fictional rule has been replaced.
  - SUPERSEDED_EVIDENCE: Replace the superseded rule with the one that replaced it, then resubmit.

## Needs a person to decide (3)

- **unknown-date** - The date of the fictional provider event is unavailable.
  - UNKNOWN_EVENT_DATE: Find the real event date from the source. Do not guess it.
- **conflicting-evidence** - Two fictional authorities disagree about the same claim.
  - CONFLICTING_EVIDENCE: A person decides which source is right. Keep both sources visible.
- **extra-secondary-rule-old-check** - A fictional trade guide says Regulation B is in force; the guide was last checked months ago.
  - BELOW_THRESHOLD: Overall evidence is thinner than the pass bar. A person decides whether it is good enough.

## Do not publish (1)

- **competitor-promotion** - Fictional RivalCloud claims its own product saves 10 percent.
  - COMPETITOR_PROMOTION: Remove the competitor's product claim, or find independent evidence for the underlying industry fact. Do not republish.
