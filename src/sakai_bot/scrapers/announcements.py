"""
Announcement scraper for Sakai.

Uses the Sakai REST API (/direct/announcement/) to extract
announcements from all enrolled courses.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from bs4 import BeautifulSoup

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Announcement, Course
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AnnouncementScraper(BaseScraper):
    """
    Scrapes announcements from Sakai courses using the REST API.

    Uses /direct/announcement/site/<siteId>.json for per-course
    announcements, with /direct/announcement/user.json as a
    supplementary source.
    """

    def __init__(self, session: SakaiSession):
        """Initialize announcement scraper."""
        super().__init__(session)

    def scrape(self, courses: List[Course]) -> List[Announcement]:
        """
        Scrape announcements from all provided courses.

        Args:
            courses: List of courses to scrape

        Returns:
            List[Announcement]: All found announcements
        """
        all_announcements: List[Announcement] = []
        seen_ids: set = set()

        # Scrape per-course announcements via REST API
        for course in courses:
            try:
                announcements = self._scrape_course_announcements(course)
                for ann in announcements:
                    if ann.id not in seen_ids:
                        seen_ids.add(ann.id)
                        all_announcements.append(ann)
                logger.debug(
                    f"Found {len(announcements)} announcements in {course.code}"
                )
            except Exception as e:
                logger.error(
                    f"Error scraping announcements for {course.code}: {e}"
                )
                continue

        # Also fetch user-level announcements (catches cross-listed/global ones)
        try:
            user_announcements = self._scrape_user_announcements(courses)
            for ann in user_announcements:
                if ann.id not in seen_ids:
                    seen_ids.add(ann.id)
                    all_announcements.append(ann)
        except Exception as e:
            logger.error(f"Error scraping user announcements: {e}")

        logger.info(f"Total announcements scraped: {len(all_announcements)}")
        return all_announcements

    def _scrape_course_announcements(
        self, course: Course
    ) -> List[Announcement]:
        """
        Scrape announcements for a single course via the REST API.

        Args:
            course: Course to scrape

        Returns:
            List[Announcement]: Announcements from this course
        """
        try:
            data = self.session.get_json(
                f"/direct/announcement/site/{course.site_id}.json"
            )
        except Exception as e:
            logger.debug(
                f"Could not get announcements for {course.code}: {e}"
            )
            return []

        announcements: List[Announcement] = []
        for item in data.get("announcement_collection", []):
            ann = self._parse_api_announcement(item, course)
            if ann:
                announcements.append(ann)

        return announcements

    def _scrape_user_announcements(
        self, courses: List[Course]
    ) -> List[Announcement]:
        """
        Scrape the user-level announcements feed.

        Args:
            courses: Known courses (for matching site IDs/titles)

        Returns:
            List[Announcement]: User-level announcements
        """
        try:
            data = self.session.get_json("/direct/announcement/user.json")
        except Exception:
            return []

        # Build lookup maps
        site_map: dict = {}
        for c in courses:
            site_map[c.site_id] = c
            site_map[c.title] = c

        announcements: List[Announcement] = []
        for item in data.get("announcement_collection", []):
            site_id = item.get("siteId", "")
            site_title = item.get("siteTitle", "")
            course = site_map.get(site_id) or site_map.get(site_title)

            # Only include announcements from our filtered courses
            if not course:
                continue

            ann = self._parse_api_announcement(
                item, course, site_title=site_title
            )
            if ann:
                announcements.append(ann)

        return announcements

    def _parse_api_announcement(
        self,
        item: dict,
        course: Optional[Course],
        site_title: str = "",
    ) -> Optional[Announcement]:
        """
        Parse an announcement from the REST API response.

        Args:
            item: Announcement dict from API
            course: Course this belongs to (may be None)
            site_title: Fallback site title if no course matched

        Returns:
            Announcement or None if parsing fails
        """
        ann_id = item.get("id") or item.get("entityId")
        title = item.get("title", "")

        if not ann_id or not title:
            return None

        # Parse body - API returns HTML body
        body = self._clean_html(item.get("body", "") or "")

        # Parse timestamp (Sakai returns epoch milliseconds)
        posted_at = self._parse_epoch_ms(item.get("createdOn"))

        # Build URL
        site_id = item.get("siteId", "")
        url = (
            f"{self.session.base_url}/portal/site/{site_id}"
            if site_id
            else None
        )

        # Get author
        author = item.get("createdByDisplayName", "")

        return Announcement(
            id=str(ann_id),
            course_code=(
                course.code
                if course
                else self.extract_course_code(site_title)
            ),
            course_title=course.title if course else site_title,
            title=title,
            content=body,
            author=author,
            posted_at=posted_at,
            url=url,
        )

    def _parse_epoch_ms(self, epoch_ms) -> Optional[datetime]:
        """Convert epoch milliseconds to datetime."""
        if not epoch_ms:
            return None
        try:
            return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            return None

    def _clean_html(self, html: str) -> str:
        """Strip HTML tags and return clean text."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator="\n", strip=True)
