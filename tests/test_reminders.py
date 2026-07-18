from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from sakai_bot.models import Assignment, AssignmentStatus, Exam
from sakai_bot.notify.reminders import ReminderService

NOW = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)


def make_assignment(due_in_hours: float | None, status=AssignmentStatus.NOT_STARTED):
    return Assignment(
        id="a1",
        course_code="DCIT 301",
        course_title="Operating Systems",
        title="Lab Report 3",
        due_date=NOW + timedelta(hours=due_in_hours) if due_in_hours is not None else None,
        status=status,
    )


def make_exam(in_hours: float | None):
    return Exam(
        id="e1",
        course_code="DCIT 305",
        course_title="Databases",
        title="Midterm exam",
        exam_date=NOW + timedelta(hours=in_hours) if in_hours is not None else None,
    )


@pytest.fixture
def service():
    store = Mock()
    store.has_been_sent.return_value = False
    notifier = Mock()
    notifier.send_message.return_value = True
    formatter = Mock()
    formatter.format_reminder.return_value = "reminder"
    return ReminderService(store, notifier, formatter, hours=[24, 3])


def test_no_reminder_outside_window(service):
    assert service.send_reminders([make_assignment(48)], [], now=NOW) == 0
    service.notifier.send_message.assert_not_called()


def test_24h_reminder_fires_inside_window(service):
    assert service.send_reminders([make_assignment(20)], [], now=NOW) == 1
    key = service.store.mark_as_sent.call_args[0][0].dedup_key
    assert key == "reminder:assignment:a1:24h"


def test_tightest_window_wins_and_suppresses_wider(service):
    # 2h before due: both 24h and 3h windows apply, one message only
    assert service.send_reminders([make_assignment(2)], [], now=NOW) == 1
    service.notifier.send_message.assert_called_once()
    keys = {call[0][0].dedup_key for call in service.store.mark_as_sent.call_args_list}
    assert keys == {"reminder:assignment:a1:3h", "reminder:assignment:a1:24h"}


def test_already_sent_window_does_not_refire(service):
    service.store.has_been_sent.return_value = True
    assert service.send_reminders([make_assignment(20)], [], now=NOW) == 0
    service.notifier.send_message.assert_not_called()


def test_past_due_items_are_skipped(service):
    assert service.send_reminders([make_assignment(-1)], [make_exam(-5)], now=NOW) == 0


def test_submitted_assignments_are_skipped(service):
    assignment = make_assignment(2, status=AssignmentStatus.SUBMITTED)
    assert service.send_reminders([assignment], [], now=NOW) == 0


def test_items_without_deadline_are_skipped(service):
    assert service.send_reminders([make_assignment(None)], [make_exam(None)], now=NOW) == 0


def test_exam_reminder_uses_exam_key(service):
    assert service.send_reminders([], [make_exam(2)], now=NOW) == 1
    keys = {call[0][0].dedup_key for call in service.store.mark_as_sent.call_args_list}
    assert "reminder:exam:e1:3h" in keys


def test_naive_due_date_is_treated_as_utc(service):
    assignment = make_assignment(20)
    assignment.due_date = assignment.due_date.replace(tzinfo=None)
    assert service.send_reminders([assignment], [], now=NOW) == 1


def test_failed_send_does_not_mark_as_sent(service):
    service.notifier.send_message.return_value = False
    assert service.send_reminders([make_assignment(20)], [], now=NOW) == 0
    service.store.mark_as_sent.assert_not_called()


def test_rescheduled_deadline_changes_content_hash(service):
    service.send_reminders([make_assignment(20)], [], now=NOW)
    first_hash = service.store.mark_as_sent.call_args[0][0].content_hash
    service.store.mark_as_sent.reset_mock()

    service.send_reminders([make_assignment(22)], [], now=NOW)
    second_hash = service.store.mark_as_sent.call_args[0][0].content_hash
    assert first_hash != second_hash
