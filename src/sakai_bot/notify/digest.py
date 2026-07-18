"""
Weekly digest of upcoming deadlines.

On runs that land in the Sunday-evening window (Africa/Accra), sends
one summary of everything due in the next 7 days. The dedup key
"digest:<sunday-date>" guarantees exactly one digest per week even
though multiple scheduled runs land in the window.
"""

import logging
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from dateutil.tz import gettz

from sakai_bot.config import get_settings
from sakai_bot.models import Assignment, Exam, NotificationType, SyntheticItem
from sakai_bot.notify.reminders import DONE_STATUSES

logger = logging.getLogger(__name__)

# Sunday (Monday=0) between 18:00 and 22:00 local time
DIGEST_WEEKDAY = 6
DIGEST_START_HOUR = 18
DIGEST_END_HOUR = 22
DIGEST_LOOKAHEAD_DAYS = 7


class DigestService:
    """Builds and sends the weekly deadline digest."""

    def __init__(self, store, notifier, formatter):
        """
        Initialize the digest service.

        Args:
            store: NotificationStore for dedup
            notifier: TelegramNotifier for sending
            formatter: MessageFormatter for message text
        """
        self.store = store
        self.notifier = notifier
        self.formatter = formatter
        self.settings = get_settings()

    def maybe_send(
        self,
        assignments: list[Assignment],
        exams: list[Exam],
        now: datetime | None = None,
    ) -> bool:
        """
        Send the weekly digest if we're in the send window and haven't yet.

        Args:
            assignments: All scraped assignments (not just new ones)
            exams: All detected exams (not just new ones)
            now: Current time, injectable for tests

        Returns:
            bool: True if a digest was sent
        """
        if not self.settings.digest_enabled:
            return False

        now = now or datetime.now(timezone.utc)
        local_now = now.astimezone(gettz(self.settings.timezone))

        if not self._in_window(local_now):
            return False

        record = self._record(local_now)
        if self.store.has_been_sent(record):
            return False

        upcoming_assignments, upcoming_exams = self._upcoming(assignments, exams, now)
        message = self.formatter.format_digest(upcoming_assignments, upcoming_exams)

        if self.notifier.send_message(message):
            self.store.mark_as_sent(record)
            logger.info(
                f"Sent weekly digest: {len(upcoming_assignments)} assignment(s), "
                f"{len(upcoming_exams)} exam(s)"
            )
            return True
        return False

    @staticmethod
    def _in_window(local_now: datetime) -> bool:
        """Check whether local time falls in the Sunday-evening window."""
        return (
            local_now.weekday() == DIGEST_WEEKDAY
            and DIGEST_START_HOUR <= local_now.hour < DIGEST_END_HOUR
        )

    @staticmethod
    def _record(local_now: datetime) -> SyntheticItem:
        """Build the once-per-week dedup record, keyed by the Sunday's date."""
        key = f"digest:{local_now.date().isoformat()}"
        return SyntheticItem(
            dedup_key=key,
            content_hash=sha256(key.encode()).hexdigest()[:16],
            notification_type=NotificationType.DIGEST,
            title="Weekly digest",
        )

    def _upcoming(
        self,
        assignments: list[Assignment],
        exams: list[Exam],
        now: datetime,
    ) -> tuple[list[Assignment], list[Exam]]:
        """Filter to items due within the lookahead window, sorted by date."""
        horizon = now + timedelta(days=DIGEST_LOOKAHEAD_DAYS)

        upcoming_assignments = sorted(
            (
                a
                for a in assignments
                if a.status not in DONE_STATUSES
                and a.due_date
                and now < self._aware(a.due_date) <= horizon
            ),
            key=lambda a: self._aware(a.due_date),
        )
        upcoming_exams = sorted(
            (e for e in exams if e.exam_date and now < self._aware(e.exam_date) <= horizon),
            key=lambda e: self._aware(e.exam_date),
        )
        return upcoming_assignments, upcoming_exams

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        """Assume UTC for naive datetimes so comparisons never raise."""
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
