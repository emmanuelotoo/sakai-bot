"""
Course scraper for Sakai.

Uses the Sakai REST API (/direct/site.json) to extract enrolled courses.
"""

import logging
from typing import List, Optional

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Course
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class CourseScraper(BaseScraper):
    """
    Scrapes enrolled courses from Sakai using the REST API.

    Uses /direct/site.json to get all sites the user is a member of.
    """

    def __init__(self, session: SakaiSession):
        """Initialize course scraper."""
        super().__init__(session)

    def scrape(self) -> List[Course]:
        """
        Scrape all enrolled courses via the REST API.

        Returns:
            List[Course]: List of enrolled courses
        """
        logger.info("Scraping enrolled courses...")

        courses: List[Course] = []

        try:
            data = self.session.get_json("/direct/site.json")
            sites = data.get("site_collection", [])

            for site in sites:
                course = self._parse_site(site)
                if course:
                    courses.append(course)

        except Exception as e:
            logger.error(f"Error scraping courses via REST API: {e}")

        logger.info(f"Found {len(courses)} enrolled courses")
        return courses

    def _parse_site(self, site: dict) -> Optional[Course]:
        """
        Parse a site dict from the REST API into a Course.

        Args:
            site: Site dict from /direct/site.json

        Returns:
            Course or None if not a valid course site
        """
        site_id = site.get("id", "")
        title = site.get("title", "")

        # Skip special sites (user workspace, admin, etc.)
        if not site_id or site_id.startswith(("~", "!")):
            return None
        if not title:
            return None

        # Skip the "My Workspace" type sites
        site_type = site.get("type", "")
        if site_type in ("myworkspace",):
            return None

        url = f"{self.session.base_url}/portal/site/{site_id}"

        return Course(
            site_id=site_id,
            code=self.extract_course_code(title),
            title=title,
            url=url,
        )

    def get_course_by_code(self, code: str) -> Optional[Course]:
        """
        Find a specific course by code.

        Args:
            code: Course code to find

        Returns:
            Course or None if not found
        """
        courses = self.scrape()
        code_upper = code.upper().replace(" ", "")

        for course in courses:
            course_code_clean = course.code.upper().replace(" ", "")
            if code_upper in course_code_clean or course_code_clean in code_upper:
                return course

        return None
