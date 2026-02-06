"""
Assignment scraper for Sakai.

Uses the Sakai REST API (/direct/assignment/) to extract
assignments and deadlines from all enrolled courses.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from bs4 import BeautifulSoup

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Assignment, AssignmentStatus, Course
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AssignmentScraper(BaseScraper):
    """
    Scrapes assignments from Sakai courses using the REST API.

    Uses /direct/assignment/site/<siteId>.json for per-course
    assignments, with /direct/assignment/my.json as a global source.
    """

    def __init__(self, session: SakaiSession):
        """Initialize assignment scraper."""
        super().__init__(session)

    def scrape(self, courses: List[Course]) -> List[Assignment]:
        """
        Scrape assignments from all provided courses.

        Args:
            courses: List of courses to scrape

        Returns:
            List[Assignment]: All found assignments
        """
        all_assignments: List[Assignment] = []
        seen_ids: set = set()

        # Build site_id -> course map
        site_map = {c.site_id: c for c in courses}

        # Primary: get all assignments via user endpoint
        try:
            data = self.session.get_json("/direct/assignment/my.json")
            for item in data.get("assignment_collection", []):
                # Only include assignments from our filtered courses
                context = item.get("context", "")
                if context not in site_map:
                    continue
                assignment = self._parse_api_assignment(item, site_map)
                if assignment and assignment.id not in seen_ids:
                    seen_ids.add(assignment.id)
                    all_assignments.append(assignment)
        except Exception as e:
            logger.error(f"Error fetching /direct/assignment/my.json: {e}")

            # Fallback: per-course scraping
            for course in courses:
                try:
                    assignments = self._scrape_course_assignments(course)
                    for a in assignments:
                        if a.id not in seen_ids:
                            seen_ids.add(a.id)
                            all_assignments.append(a)
                except Exception as exc:
                    logger.error(
                        f"Error scraping assignments for {course.code}: {exc}"
                    )

        logger.info(f"Total assignments scraped: {len(all_assignments)}")
        return all_assignments

    def _scrape_course_assignments(
        self, course: Course
    ) -> List[Assignment]:
        """
        Scrape assignments for a single course via the REST API.

        Args:
            course: Course to scrape

        Returns:
            List[Assignment]: Assignments from this course
        """
        try:
            data = self.session.get_json(
                f"/direct/assignment/site/{course.site_id}.json"
            )
        except Exception as e:
            logger.debug(
                f"Could not get assignments for {course.code}: {e}"
            )
            return []

        site_map = {course.site_id: course}
        assignments: List[Assignment] = []
        for item in data.get("assignment_collection", []):
            a = self._parse_api_assignment(item, site_map)
            if a:
                assignments.append(a)

        return assignments

    def _parse_api_assignment(
        self,
        item: dict,
        site_map: dict,
    ) -> Optional[Assignment]:
        """
        Parse an assignment from the REST API response.

        Args:
            item: Assignment dict from API
            site_map: Mapping of site_id -> Course

        Returns:
            Assignment or None if parsing fails
        """
        assign_id = item.get("id") or item.get("entityId")
        title = item.get("title", "")

        if not assign_id or not title:
            return None

        # Find the matching course
        context = item.get("context", "")
        course = site_map.get(context)

        # Extract course code from context if no match (context is like "DCIT-201-1-S1-2425")
        course_code = course.code if course else context.replace("-", " ")
        course_title = course.title if course else context

        # Parse description (HTML)
        description = self._clean_html(item.get("instructions", "") or "")

        # Parse dates (Sakai returns ISO strings or epoch)
        due_date = self._parse_date_field(item.get("dueTime") or item.get("dueTimeString"))
        open_date = self._parse_date_field(item.get("openTime") or item.get("openTimeString"))
        close_date = self._parse_date_field(item.get("closeTime") or item.get("closeTimeString"))

        # Determine status
        status = self._determine_status(item, due_date, close_date)

        # Max points
        max_points = None
        try:
            max_points = float(item.get("gradeScaleMaxPoints", 0) or 0)
        except (ValueError, TypeError):
            pass

        # Build URL
        site_id = item.get("context", "")
        url = (
            f"{self.session.base_url}/portal/site/{site_id}"
            if site_id
            else None
        )

        return Assignment(
            id=str(assign_id),
            course_code=course_code,
            course_title=course_title,
            title=title,
            description=description,
            due_date=due_date,
            open_date=open_date,
            close_date=close_date,
            status=status,
            max_points=max_points if max_points else None,
            url=url,
        )

    def _parse_date_field(self, value) -> Optional[datetime]:
        """Parse a date field that could be epoch dict, ISO string, or epoch ms."""
        if not value:
            return None

        # If it's a dict with 'epochSecond' (Sakai sometimes returns this)
        if isinstance(value, dict):
            epoch = value.get("epochSecond") or value.get("time")
            if epoch:
                try:
                    return datetime.fromtimestamp(int(epoch), tz=timezone.utc)
                except (ValueError, TypeError, OSError):
                    pass
            return None

        # If it's a number (epoch ms)
        if isinstance(value, (int, float)):
            try:
                # If > year 3000 in seconds, it's probably milliseconds
                if value > 32503680000:
                    value = value / 1000
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                return None

        # If it's a string, try parsing
        if isinstance(value, str):
            return self.parse_date(value)

        return None

    def _determine_status(
        self,
        item: dict,
        due_date: Optional[datetime],
        close_date: Optional[datetime],
    ) -> AssignmentStatus:
        """Determine assignment status from API data."""
        # Check submission status from API
        status_str = (item.get("status") or "").lower()

        if "submitted" in status_str:
            return AssignmentStatus.SUBMITTED
        if "graded" in status_str or "returned" in status_str:
            return AssignmentStatus.GRADED

        now = datetime.now(tz=timezone.utc)

        if close_date and now > close_date:
            return AssignmentStatus.CLOSED
        if due_date and now > due_date:
            return AssignmentStatus.LATE

        return AssignmentStatus.NOT_STARTED

    def _clean_html(self, html: str) -> str:
        """Strip HTML tags and return clean text."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator="\n", strip=True)
