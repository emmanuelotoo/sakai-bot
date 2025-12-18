"""
Main orchestrator for Sakai Monitoring Bot.

Coordinates the full monitoring workflow:
1. Login to Sakai
2. Scrape all courses
3. Scrape announcements, assignments, and exams
4. Check for new/updated items (deduplication)
5. Send WhatsApp notifications
6. Record sent notifications
"""

import logging
import sys
from typing import List, Tuple

from sakai_bot.auth import SakaiSession
from sakai_bot.config import get_settings, setup_logging
from sakai_bot.db import NotificationStore
from sakai_bot.models import Announcement, Assignment, Exam
from sakai_bot.notify import MessageFormatter, WhatsAppNotifier
from sakai_bot.scrapers import (
    AnnouncementScraper,
    AssignmentScraper,
    CourseScraper,
    ExamDetector,
)

logger = logging.getLogger(__name__)


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
        self.whatsapp = WhatsAppNotifier()
        self.formatter = MessageFormatter()
        
        # Track stats
        self.stats = {
            "courses_scraped": 0,
            "announcements_found": 0,
            "assignments_found": 0,
            "exams_found": 0,
            "notifications_sent": 0,
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
                    logger.warning("No courses found. Check login credentials.")
                    return False
                
                self.stats["courses_scraped"] = len(courses)
                logger.info(f"Found {len(courses)} enrolled courses")
                
                # Step 2: Scrape announcements
                new_announcements = self._process_announcements(session, courses)
                
                # Step 3: Scrape assignments
                new_assignments = self._process_assignments(session, courses)
                
                # Step 4: Detect exams
                new_exams = self._process_exams(session, courses, new_announcements)
                
                # Step 5: Send notifications
                self._send_notifications(new_announcements, new_assignments, new_exams)
            
            # Log summary
            self._log_summary()
            return True
            
        except Exception as e:
            logger.error(f"Monitor failed with error: {e}", exc_info=True)
            self.stats["errors"] += 1
            
            # Try to send error notification
            try:
                error_msg = self.formatter.format_error(str(e))
                self.whatsapp.send_message(error_msg)
            except Exception:
                pass  # Don't fail on notification error
            
            return False
    
    def _scrape_courses(self, session: SakaiSession) -> List:
        """Scrape enrolled courses."""
        scraper = CourseScraper(session)
        return scraper.scrape()
    
    def _process_announcements(
        self, 
        session: SakaiSession, 
        courses: List
    ) -> List[Announcement]:
        """
        Scrape and filter new announcements.
        
        Args:
            session: Authenticated session
            courses: List of courses to scrape
            
        Returns:
            List of new/updated announcements
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
            f"Announcements: {len(all_announcements)} total, "
            f"{len(new_announcements)} new"
        )
        return new_announcements
    
    def _process_assignments(
        self, 
        session: SakaiSession, 
        courses: List
    ) -> List[Assignment]:
        """
        Scrape and filter new assignments.
        
        Args:
            session: Authenticated session
            courses: List of courses to scrape
            
        Returns:
            List of new/updated assignments
        """
        scraper = AssignmentScraper(session)
        all_assignments = scraper.scrape(courses)
        self.stats["assignments_found"] = len(all_assignments)
        
        # Filter to new/updated only
        new_assignments = []
        for assignment in all_assignments:
            if not self.notification_store.has_been_sent(assignment):
                new_assignments.append(assignment)
        
        logger.info(
            f"Assignments: {len(all_assignments)} total, "
            f"{len(new_assignments)} new"
        )
        return new_assignments
    
    def _process_exams(
        self, 
        session: SakaiSession, 
        courses: List,
        announcements: List[Announcement]
    ) -> List[Exam]:
        """
        Detect and filter new exams.
        
        Args:
            session: Authenticated session
            courses: List of courses
            announcements: Already scraped announcements for keyword detection
            
        Returns:
            List of new exam detections
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
        
        logger.info(
            f"Exams: {len(all_exams)} total, "
            f"{len(new_exams)} new"
        )
        return new_exams
    
    def _send_notifications(
        self,
        announcements: List[Announcement],
        assignments: List[Assignment],
        exams: List[Exam],
    ) -> None:
        """
        Send WhatsApp notifications for new items.
        
        Args:
            announcements: New announcements to notify
            assignments: New assignments to notify
            exams: New exams to notify
        """
        total_new = len(announcements) + len(assignments) + len(exams)
        
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
        
        # Send summary if multiple items
        if total_new > 1:
            summary = self.formatter.format_summary(
                announcements_count=len(announcements),
                assignments_count=len(assignments),
                exams_count=len(exams),
            )
            self.whatsapp.send_message(summary)
    
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
            if self.whatsapp.send_message(message):
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
        logger.info(f"Notifications sent:   {self.stats['notifications_sent']}")
        logger.info(f"Errors:               {self.stats['errors']}")
        logger.info("=" * 50)


def main() -> int:
    """
    Entry point for the Sakai Monitoring Bot.
    
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
    
    # Run the monitor
    monitor = SakaiMonitor()
    success = monitor.run()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
