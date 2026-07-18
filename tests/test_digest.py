from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from sakai_bot.models import Assignment, AssignmentStatus, Exam
from sakai_bot.notify.digest import DigestService

# Sunday 2026-07-19, 19:00 Africa/Accra (== UTC)
SUNDAY_EVENING = datetime(2026, 7, 19, 19, 0, tzinfo=timezone.utc)


def make_assignment(due_in_days: float, status=AssignmentStatus.NOT_STARTED):
    return Assignment(
        id=f"a-{due_in_days}",
        course_code="DCIT 301",
        course_title="Operating Systems",
        title="Lab Report",
        due_date=SUNDAY_EVENING + timedelta(days=due_in_days),
        status=status,
    )


def make_exam(in_days: float):
    return Exam(
        id=f"e-{in_days}",
        course_code="DCIT 305",
        course_title="Databases",
        title="Midterm",
        exam_date=SUNDAY_EVENING + timedelta(days=in_days),
    )


@pytest.fixture
def service():
    store = Mock()
    store.has_been_sent.return_value = False
    notifier = Mock()
    notifier.send_message.return_value = True
    formatter = Mock()
    formatter.format_digest.return_value = "digest"
    return DigestService(store, notifier, formatter)


def test_sends_on_sunday_evening(service):
    assert service.maybe_send([make_assignment(2)], [], now=SUNDAY_EVENING) is True
    service.notifier.send_message.assert_called_once()
    key = service.store.mark_as_sent.call_args[0][0].dedup_key
    assert key == "digest:2026-07-19"


def test_skips_outside_window(service):
    monday = SUNDAY_EVENING + timedelta(days=1)
    assert service.maybe_send([make_assignment(2)], [], now=monday) is False

    sunday_morning = SUNDAY_EVENING.replace(hour=9)
    assert service.maybe_send([make_assignment(2)], [], now=sunday_morning) is False
    service.notifier.send_message.assert_not_called()


def test_sends_only_once_per_week(service):
    service.store.has_been_sent.return_value = True
    assert service.maybe_send([make_assignment(2)], [], now=SUNDAY_EVENING) is False
    service.notifier.send_message.assert_not_called()


def test_filters_to_next_seven_days(service):
    assignments = [
        make_assignment(2),  # in window
        make_assignment(10),  # too far out
        make_assignment(-1),  # already past
        make_assignment(3, status=AssignmentStatus.SUBMITTED),  # done
    ]
    exams = [make_exam(5), make_exam(20)]

    service.maybe_send(assignments, exams, now=SUNDAY_EVENING)

    passed_assignments, passed_exams = service.formatter.format_digest.call_args[0]
    assert [a.id for a in passed_assignments] == ["a-2"]
    assert [e.id for e in passed_exams] == ["e-5"]


def test_sends_even_when_week_is_empty(service):
    assert service.maybe_send([], [], now=SUNDAY_EVENING) is True
    service.formatter.format_digest.assert_called_once_with([], [])


def test_disabled_via_settings(service, monkeypatch):
    from sakai_bot.config import get_settings

    monkeypatch.setenv("DIGEST_ENABLED", "false")
    get_settings.cache_clear()
    disabled = DigestService(Mock(), Mock(), Mock())
    assert disabled.maybe_send([make_assignment(2)], [], now=SUNDAY_EVENING) is False


def test_failed_send_does_not_mark_as_sent(service):
    service.notifier.send_message.return_value = False
    assert service.maybe_send([], [], now=SUNDAY_EVENING) is False
    service.store.mark_as_sent.assert_not_called()
