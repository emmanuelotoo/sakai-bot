"""
Deadline reminders for assignments and exams.

Sends a Telegram reminder when an item enters a reminder window
(e.g. 24h and 3h before it is due). Each window fires at most once,
tracked via the notification store with keys like
"reminder:assignment:123:3h".
"""

import logging
from datetime import datetime, timezone
from hashlib import sha256

from sakai_bot.config import get_settings
from sakai_bot.models import Assignment, AssignmentStatus, Exam, SyntheticItem

logger = logging.getLogger(__name__)

# Assignment statuses that no longer need reminders
DONE_STATUSES = {
    AssignmentStatus.SUBMITTED,
    AssignmentStatus.GRADED,
    AssignmentStatus.CLOSED,
}


class ReminderService:
    """
    Computes and sends deadline reminders.

    If multiple windows apply at once (e.g. an item first seen 2h before
    its deadline), only the tightest reminder is sent and the larger
    windows are marked as sent so they never fire afterwards.
    """

    def __init__(self, store, notifier, formatter, hours: list[int] | None = None):
        """
        Initialize the reminder service.

        Args:
            store: NotificationStore for dedup
            notifier: TelegramNotifier for sending
            formatter: MessageFormatter for message text
            hours: Reminder thresholds in hours (defaults to settings)
        """
        self.store = store
        self.notifier = notifier
        self.formatter = formatter
        self.hours = sorted(hours or get_settings().reminder_hours_list, reverse=True)

    def send_reminders(
        self,
        assignments: list[Assignment],
        exams: list[Exam],
        now: datetime | None = None,
    ) -> int:
        """
        Send reminders for items inside a reminder window.

        Args:
            assignments: All scraped assignments (not just new ones)
            exams: All detected exams (not just new ones)
            now: Current time, injectable for tests

        Returns:
            int: Number of reminders sent
        """
        now = now or datetime.now(timezone.utc)
        sent = 0

        for item, due in self._items_with_deadlines(assignments, exams):
            hours_left = (due - now).total_seconds() / 3600
            if hours_left <= 0:
                continue

            applicable = [h for h in self.hours if hours_left <= h]
            if not applicable:
                continue

            tightest = min(applicable)
            if self.store.has_been_sent(self._record(item, tightest, due)):
                continue

            message = self.formatter.format_reminder(item, due, hours_left)
            if self.notifier.send_message(message):
                sent += 1
                # Mark every applicable window so a wider reminder never
                # fires after a tighter one was already sent.
                for h in applicable:
                    self.store.mark_as_sent(self._record(item, h, due))
                logger.info(f"Sent {tightest}h reminder for: {item.title}")

        return sent

    def _items_with_deadlines(
        self, assignments: list[Assignment], exams: list[Exam]
    ) -> list[tuple[Assignment | Exam, datetime]]:
        """Pair each remindable item with its (timezone-aware) deadline."""
        pairs: list[tuple[Assignment | Exam, datetime]] = []

        for assignment in assignments:
            if assignment.status in DONE_STATUSES:
                continue
            due = self._ensure_aware(assignment.due_date)
            if due:
                pairs.append((assignment, due))

        for exam in exams:
            due = self._ensure_aware(exam.exam_date)
            if due:
                pairs.append((exam, due))

        return pairs

    @staticmethod
    def _ensure_aware(dt: datetime | None) -> datetime | None:
        """Assume UTC for naive datetimes so comparisons never raise."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _record(item: Assignment | Exam, hours: int, due: datetime) -> SyntheticItem:
        """Build the dedup record for one reminder window of one item."""
        return SyntheticItem(
            dedup_key=f"reminder:{item.dedup_key}:{hours}h",
            content_hash=sha256(due.isoformat().encode()).hexdigest()[:16],
            notification_type=item.notification_type,
            title=item.title,
            course_code=item.course_code,
        )
