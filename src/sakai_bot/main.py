"""
Main orchestrator for Sakai Monitoring Bot.

Coordinates the full monitoring workflow:
1. Login to Sakai
2. Scrape all courses
3. Scrape announcements, assignments, and exams
4. Check for new/updated items (deduplication)
5. Send Telegram notifications
6. Record sent notifications
"""

import logging
import sys
import time

from sakai_bot.auth import SakaiSession
from sakai_bot.auth.sakai_session import SakaiAuthError
from sakai_bot.config import get_settings, setup_logging
from sakai_bot.db import NotificationStore
from sakai_bot.models import Announcement, Assignment, Exam, Resource
from sakai_bot.notify import (
    DigestService,
    MessageFormatter,
    ReminderService,
    TelegramNotifier,
)
from sakai_bot.scrapers import (
    AnnouncementScraper,
    AssignmentScraper,
    CourseScraper,
    ExamDetector,
    ResourceScraper,
)

logger = logging.getLogger(__name__)


def notify_fallback(telegram, reason: str | None, count: int) -> bool:
    """
    Send a Telegram heads-up when course filtering had to fall back.

    Returns True if a message was sent, False otherwise. Never raises.
    """
    if not reason:
        return False
    msg = f"⚠️ Course filter fallback: {reason}. " f"Monitoring {count} course(s) this run."
    logger.warning(msg)
    try:
        telegram.send_message(msg)
        return True
    except Exception:
        return False


class SakaiMonitor:
    """
    Main orchestrator for Sakai monitoring.

    Coordinates all components to provide end-to-end monitoring
    with deduplication and notifications.
    """

    def __init__(self):
        """Initialize the monitor with all components."""
        self.settings = get_settings()
        self.notification_store = NotificationStore()
        self.telegram = TelegramNotifier()
        self.formatter = MessageFormatter()

        # Track stats
        self.stats = {
            "courses_scraped": 0,
            "announcements_found": 0,
            "assignments_found": 0,
            "exams_found": 0,
            "resources_found": 0,
            "notifications_sent": 0,
            "reminders_sent": 0,
            "errors": 0,
        }

    def run(self) -> bool:
        """
        Execute full monitoring workflow.

        Returns:
            bool: True if completed successfully
        """
        logger.info("=" * 50)
        logger.info("Starting Sakai Monitoring Bot")
        logger.info("=" * 50)

        try:
            # Use context manager for automatic login/logout
            with SakaiSession() as session:
                # Step 1: Get enrolled courses
                courses = self._scrape_courses(session)
                if not courses:
                    logger.warning(
                        "Logged in, but found no enrolled sites. "
                        "Check your Sakai enrollment or credentials."
                    )
                    return False

                self.stats["courses_scraped"] = len(courses)
                logger.info(f"Found {len(courses)} enrolled courses")

                # Step 2: Scrape announcements
                all_announcements, new_announcements = self._process_announcements(session, courses)

                # Step 3: Scrape assignments
                all_assignments, new_assignments = self._process_assignments(session, courses)

                # Step 4: Detect exams (from ALL announcements, so exams
                # announced weeks ago still feed reminders and the digest)
                all_exams, new_exams = self._process_exams(session, courses, all_announcements)

                # Step 5: Scrape new course resources
                new_resources = self._process_resources(session, courses)

                # Step 6: Send notifications for new items
                self._send_notifications(
                    new_announcements, new_assignments, new_exams, new_resources
                )

                # Step 7: Deadline reminders (24h/3h before due)
                self._send_reminders(all_assignments, all_exams)

                # Step 8: Weekly digest (Sunday evenings)
                self._maybe_send_digest(all_assignments, all_exams)

            # Log summary
            self._log_summary()
            return True
        except SakaiAuthError:
            raise  # propagate so main() can retry on transient auth failures

        except Exception as e:
            logger.error(f"Monitor failed with error: {e}", exc_info=True)
            self.stats["errors"] += 1

            # Try to send error notification
            try:
                error_msg = self.formatter.format_error(str(e))
                self.telegram.send_message(error_msg)
            except Exception:
                pass  # Don't fail on notification error

            return False

    def _scrape_courses(self, session: SakaiSession) -> list:
        """Scrape enrolled courses, warning if filtering had to fall back."""
        scraper = CourseScraper(session)
        courses = scraper.scrape()
        notify_fallback(self.telegram, scraper.fallback_reason, len(courses))
        return courses

    def _process_announcements(
        self, session: SakaiSession, courses: list
    ) -> tuple[list[Announcement], list[Announcement]]:
        """
        Scrape announcements and identify new ones.

        Args:
            session: Authenticated session
            courses: List of courses to scrape

        Returns:
            Tuple of (all announcements, new/updated announcements)
        """
        scraper = AnnouncementScraper(session)
        all_announcements = scraper.scrape(courses)
        self.stats["announcements_found"] = len(all_announcements)

        # Filter to new/updated only
        new_announcements = []
        for announcement in all_announcements:
            if not self.notification_store.has_been_sent(announcement):
                new_announcements.append(announcement)

        logger.info(
            f"Announcements: {len(all_announcements)} total, " f"{len(new_announcements)} new"
        )
        return all_announcements, new_announcements

    def _process_assignments(
        self, session: SakaiSession, courses: list
    ) -> tuple[list[Assignment], list[Assignment]]:
        """
        Scrape assignments and identify new ones.

        Args:
            session: Authenticated session
            courses: List of courses to scrape

        Returns:
            Tuple of (all assignments, new/updated assignments)
        """
        scraper = AssignmentScraper(session)
        all_assignments = scraper.scrape(courses)
        self.stats["assignments_found"] = len(all_assignments)

        # Filter to new/updated only
        new_assignments = []
        for assignment in all_assignments:
            if not self.notification_store.has_been_sent(assignment):
                new_assignments.append(assignment)

        logger.info(f"Assignments: {len(all_assignments)} total, " f"{len(new_assignments)} new")
        return all_assignments, new_assignments

    def _process_exams(
        self, session: SakaiSession, courses: list, announcements: list[Announcement]
    ) -> tuple[list[Exam], list[Exam]]:
        """
        Detect exams and identify new ones.

        Args:
            session: Authenticated session
            courses: List of courses
            announcements: All scraped announcements for keyword detection

        Returns:
            Tuple of (all detected exams, new exam detections)
        """
        detector = ExamDetector(session)

        # Pass all announcements (not just new) for comprehensive detection
        # but we'll deduplicate the results
        all_exams = detector.scrape(courses, announcements)
        self.stats["exams_found"] = len(all_exams)

        # Filter to new only
        new_exams = []
        for exam in all_exams:
            if not self.notification_store.has_been_sent(exam):
                new_exams.append(exam)

        logger.info(f"Exams: {len(all_exams)} total, " f"{len(new_exams)} new")
        return all_exams, new_exams

    def _process_resources(self, session: SakaiSession, courses: list) -> list[Resource]:
        """
        Scrape recently uploaded course resources and filter to new ones.

        Never raises — a resources failure must not block the main pipeline.

        Args:
            session: Authenticated session
            courses: List of courses to scrape

        Returns:
            List of new/updated resources
        """
        try:
            scraper = ResourceScraper(session)
            all_resources = scraper.scrape(courses)
            self.stats["resources_found"] = len(all_resources)

            new_resources = []
            for resource in all_resources:
                if not self.notification_store.has_been_sent(resource):
                    new_resources.append(resource)

            logger.info(f"Resources: {len(all_resources)} recent, " f"{len(new_resources)} new")
            return new_resources
        except Exception as e:
            logger.error(f"Resource scraping failed: {e}")
            self.stats["errors"] += 1
            return []

    def _send_reminders(self, assignments: list[Assignment], exams: list[Exam]) -> None:
        """
        Send deadline reminders for items approaching their due date.

        Never raises — a reminder failure must not block the main pipeline.
        """
        try:
            service = ReminderService(self.notification_store, self.telegram, self.formatter)
            sent = service.send_reminders(assignments, exams)
            self.stats["reminders_sent"] = sent
            if sent:
                logger.info(f"Sent {sent} deadline reminder(s)")
        except Exception as e:
            logger.error(f"Deadline reminders failed: {e}")
            self.stats["errors"] += 1

    def _maybe_send_digest(self, assignments: list[Assignment], exams: list[Exam]) -> None:
        """
        Send the weekly digest if we're in the Sunday-evening window.

        Never raises — a digest failure must not block the main pipeline.
        """
        try:
            service = DigestService(self.notification_store, self.telegram, self.formatter)
            service.maybe_send(assignments, exams)
        except Exception as e:
            logger.error(f"Weekly digest failed: {e}")
            self.stats["errors"] += 1

    def _send_notifications(
        self,
        announcements: list[Announcement],
        assignments: list[Assignment],
        exams: list[Exam],
        resources: list[Resource] | None = None,
    ) -> None:
        """
        Send Telegram notifications for new items.

        Args:
            announcements: New announcements to notify
            assignments: New assignments to notify
            exams: New exams to notify
            resources: New course resources to notify
        """
        resources = resources or []
        total_new = len(announcements) + len(assignments) + len(exams) + len(resources)

        if total_new == 0:
            logger.info("No new items to notify")
            return

        logger.info(f"Sending {total_new} notifications...")

        # Send announcements
        for announcement in announcements:
            self._send_and_record(
                announcement,
                self.formatter.format_announcement(announcement),
            )

        # Send assignments
        for assignment in assignments:
            self._send_and_record(
                assignment,
                self.formatter.format_assignment(assignment),
            )

        # Send exams
        for exam in exams:
            self._send_and_record(
                exam,
                self.formatter.format_exam(exam),
            )

        # Send new course files
        for resource in resources:
            self._send_and_record(
                resource,
                self.formatter.format_resource(resource),
            )

        # Send summary if multiple items
        if total_new > 1:
            summary = self.formatter.format_summary(
                announcements_count=len(announcements),
                assignments_count=len(assignments),
                exams_count=len(exams),
                resources_count=len(resources),
            )
            self.telegram.send_message(summary)

    def _send_and_record(self, item, message: str) -> bool:
        """
        Send notification and record if successful.

        Args:
            item: The item being notified (Announcement, Assignment, or Exam)
            message: Formatted message to send

        Returns:
            bool: True if sent and recorded successfully
        """
        try:
            if self.telegram.send_message(message):
                self.notification_store.mark_as_sent(item)
                self.stats["notifications_sent"] += 1
                logger.debug(f"Sent notification for: {item.title}")
                return True
            else:
                logger.warning(f"Failed to send notification for: {item.title}")
                return False
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            self.stats["errors"] += 1
            return False

    def _log_summary(self) -> None:
        """Log execution summary."""
        logger.info("=" * 50)
        logger.info("Monitoring Complete - Summary")
        logger.info("=" * 50)
        logger.info(f"Courses scraped:      {self.stats['courses_scraped']}")
        logger.info(f"Announcements found:  {self.stats['announcements_found']}")
        logger.info(f"Assignments found:    {self.stats['assignments_found']}")
        logger.info(f"Exams detected:       {self.stats['exams_found']}")
        logger.info(f"Recent resources:     {self.stats['resources_found']}")
        logger.info(f"Notifications sent:   {self.stats['notifications_sent']}")
        logger.info(f"Reminders sent:       {self.stats['reminders_sent']}")
        logger.info(f"Errors:               {self.stats['errors']}")
        logger.info("=" * 50)


def main() -> int:
    """
    Entry point for the Sakai Monitoring Bot.

    Retries the full monitoring run on transient auth/network errors.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    # Setup logging
    setup_logging()

    try:
        # Validate configuration early
        settings = get_settings()
        logger.debug(f"Loaded configuration for {settings.sakai_base_url}")
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("Please check your environment variables.", file=sys.stderr)
        return 1

    # Run the monitor with retries for transient failures
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        monitor = SakaiMonitor()
        try:
            success = monitor.run()
            return 0 if success else 1
        except SakaiAuthError as e:
            if attempt < max_attempts:
                wait = 60 * attempt
                logger.warning(
                    f"Run attempt {attempt}/{max_attempts} failed with auth error. "
                    f"Retrying in {wait}s…"
                )
                time.sleep(wait)
            else:
                logger.error(f"All {max_attempts} run attempts failed: {e}")
                # Transient server-side issue — exit 0 so the workflow
                # doesn't report a failure for something out of our control.
                # The next scheduled run will try again.
                retry_message = (
                    f"Sakai server unreachable after {max_attempts} attempts. "
                    "Will retry on next scheduled run."
                )
                logger.info(retry_message)
                try:
                    formatter = MessageFormatter()
                    notifier = TelegramNotifier()
                    notifier.send_message(formatter.format_error(retry_message))
                except Exception:
                    pass
                return 0


if __name__ == "__main__":
    sys.exit(main())
