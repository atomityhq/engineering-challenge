"""Freshness distinguishes publication, event and effective dates, applicability and unknown/conflicting dates."""

import re
from pathlib import Path

import pytest

from g2_gate import codes


@pytest.mark.parametrize("event_date, status, decision", [
    ("2026-10-06", "current", "pass"),       # same day
    ("2026-09-06", "current", "pass"),       # exactly 30 days: inside the window
    ("2026-09-05", "stale", "revise"),       # 31 days: outside
])
def test_news_window_boundary(make_case, evaluate, event_date, status, decision):
    report = evaluate(make_case(event_date=event_date, published_at=event_date))
    assert report.freshness.status.value == status
    assert report.decision.value == decision


def test_freshness_uses_fixture_as_of_not_the_clock(make_case, evaluate):
    case = make_case()
    assert evaluate(case).freshness.status.value == "current"
    later = evaluate(case, as_of="2026-12-01")
    assert later.freshness.status.value == "stale"
    assert later.freshness.reference_age_days == 59
    assert later.as_of.isoformat() == "2026-12-01"


def test_gate_source_never_reads_the_system_clock():
    source = "\n".join(p.read_text(encoding="utf-8") for p in (Path(__file__).parents[1] / "g2_gate").glob("*.py"))
    clock = r"\b(date\.today|datetime\.(now|utcnow|today)|time\.(time|localtime|gmtime|monotonic)|fromtimestamp)\("
    assert not re.search(clock, source)


def test_old_publication_does_not_make_news_stale_if_event_is_recent(make_case, evaluate):
    report = evaluate(make_case(published_at="2026-10-05", event_date="2026-10-01"))
    assert report.freshness.status.value == "current"


def test_publication_date_is_not_a_substitute_for_event_date(make_case, evaluate):
    report = evaluate(make_case(event_date=None, published_at="2026-10-05"))
    assert report.freshness.status.value == "unknown"
    assert "not a substitute" in report.freshness.explanation


def test_old_rule_in_force_has_no_age_penalty(make_case, evaluate):
    report = evaluate(make_case(content_type="regulation", published_at="2015-01-01", event_date="2015-01-01",
                                effective_from="2016-01-01"))
    assert report.freshness.status.value == "current"
    assert report.freshness.reference_age_days > 3900
    assert report.criteria["temporal_validity"].score == 1.0
    assert report.decision.value == "pass"


def test_future_rule_passes_freshness_but_is_not_currently_applicable(make_case, evaluate):
    report = evaluate(make_case(content_type="regulation", current_status="adopted_not_applicable",
                                effective_from="2027-01-01"))
    fresh = report.freshness
    assert (fresh.status.value, fresh.passed, fresh.currently_applicable) == ("not_yet_applicable", True, False)
    assert fresh.applicability.value == "not_yet_applicable"
    assert fresh.presentation_constraint.startswith("Present as adopted but not applicable until 2027-01-01")


def test_future_rule_becomes_a_conflict_once_its_date_has_passed(make_case, evaluate):
    case = make_case(content_type="regulation", current_status="adopted_not_applicable", effective_from="2027-01-01")
    report = evaluate(case, as_of="2027-02-01")
    assert report.freshness.status.value == "conflicting"
    assert codes.STATUS_DATE_CONFLICT in report.freshness.issue_codes
    assert report.decision.value == "human_review"


@pytest.mark.parametrize("overrides, issue", [
    ({"published_at": "2026-10-12"}, codes.DATE_AFTER_AS_OF),
    ({"last_verified_at": "2026-10-07"}, codes.DATE_AFTER_AS_OF),
    ({"content_type": "regulation", "effective_from": "2027-03-01"}, codes.STATUS_DATE_CONFLICT),
])
def test_conflicting_dates_route_to_human_review(make_case, evaluate, overrides, issue):
    report = evaluate(make_case(**overrides))
    assert report.freshness.status.value == "conflicting"
    assert issue in report.freshness.issue_codes
    assert report.criteria["temporal_validity"].score is None
    assert report.decision.value == "human_review"


def test_future_dated_news_event_is_not_assumed_to_have_happened(make_case, evaluate):
    report = evaluate(make_case(event_date="2026-11-02"))
    assert report.freshness.status.value == "future_event"
    assert report.freshness.passed is None
    assert report.decision.value == "human_review"


@pytest.mark.parametrize("last_verified_at, score", [
    ("2026-10-06", 1.0),
    ("2026-09-06", 1.0),   # 30 days: inside the verification window
    ("2026-09-05", 0.5),   # 31 days: status not recently verified
    (None, 0.5),
])
def test_verification_recency_grades_temporal_validity(make_case, evaluate, last_verified_at, score):
    report = evaluate(make_case(last_verified_at=last_verified_at))
    assert report.criteria["temporal_validity"].score == score
    assert report.freshness.status.value == "current", "verification recency grades the score; it is not a gate"


def test_superseded_status_wins_over_dates(make_case, evaluate):
    report = evaluate(make_case(current_status="superseded", superseded=True, event_date=None))
    assert report.freshness.status.value == "superseded"
    assert report.decision.value == "revise"


def test_supersession_metadata_disagreement_is_reported(make_case, evaluate):
    report = evaluate(make_case(current_status="superseded", superseded=False))
    assert report.hard_checks["evidence_not_superseded"].status == "fail"
    assert codes.SUPERSESSION_METADATA_INCONSISTENT in report.reason_codes
    assert report.decision.value == "revise"


def test_explanation_names_the_date_used_and_its_type(make_case, evaluate):
    report = evaluate(make_case(event_date="2026-09-20", published_at="2026-10-05"))
    fresh = report.freshness
    assert fresh.reference_date_type == "event_date"
    assert fresh.reference_date.isoformat() == "2026-09-20"
    assert "2026-09-20" in fresh.explanation and "16 days" in fresh.explanation
    assert set(fresh.dates) == {"published_at", "event_date", "effective_from", "last_verified_at"}


@pytest.mark.parametrize("overrides, code, field", [
    ({"published_at": "2026-10-12"}, codes.DATE_AFTER_AS_OF, "published_at"),
    ({"last_verified_at": "2026-10-07"}, codes.DATE_AFTER_AS_OF, "last_verified_at"),
    ({"current_status": "unknown"}, codes.UNKNOWN_CURRENT_STATUS, "current_status"),
    ({"event_date": None}, codes.UNKNOWN_EVENT_DATE, "event_date"),
    ({"content_type": "regulation", "effective_from": "2025-01-01", "event_date": "2026-11-01"},
     codes.FUTURE_EVENT_DATE, "event_date"),
    ({"content_type": "regulation", "effective_from": None}, codes.UNKNOWN_EFFECTIVE_DATE, "effective_from"),
])
def test_reasons_name_the_field_that_caused_them(make_case, evaluate, overrides, code, field):
    report = evaluate(make_case(**overrides))
    assert {"code": code, "field": field} in [i.model_dump() for i in report.freshness.issues]
    assert (code, field) in [(r.code, r.subject) for r in report.reasons]


@pytest.mark.parametrize("overrides, temporal_validity", [
    ({"last_verified_at": None}, 0.5),
    ({"last_verified_at": None, "event_date": "2025-01-01"}, 0.0),
    ({"last_verified_at": None, "event_date": None}, None),
    ({"last_verified_at": "2025-01-01", "current_status": "superseded", "superseded": True}, 0.0),
])
def test_unverified_status_message_matches_the_actual_score(make_case, evaluate, overrides, temporal_validity):
    report = evaluate(make_case(**overrides))
    assert report.criteria["temporal_validity"].score == temporal_validity
    message = next(r.message for r in report.reasons if r.code == codes.STATUS_NOT_RECENTLY_VERIFIED)
    assert ("scored 0.5" in message) == (temporal_validity == 0.5)


def test_verification_window_is_labelled_as_a_demo_convention(make_case, evaluate):
    verification = evaluate(make_case()).freshness.verification
    assert "not a validated threshold" in verification.window_note
