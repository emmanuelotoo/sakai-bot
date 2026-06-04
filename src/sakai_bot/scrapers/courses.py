"""
Course scraper for Sakai.

Uses the Sakai REST API (/direct/site.json) to extract enrolled courses,
auto-detecting the current academic term and filtering by course level.
"""

import logging
import re

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Course
from sakai_bot.scrapers.base import BaseScraper
from sakai_bot.scrapers.term import latest_term, parse_term

logger = logging.getLogger(__name__)


class CourseScraper(BaseScraper):
    """
    Scrapes enrolled courses from Sakai using the REST API.

    Uses /direct/site.json to get all sites the user is a member of, then
    selects the current term (auto-detected, or a validated CURRENT_SEMESTER
    override) and applies the optional course-level filter. Never returns an
    empty list when sites are enrolled; records why in `fallback_reason`.
    """

    def __init__(self, session: SakaiSession):
        """Initialize course scraper."""
        super().__init__(session)
        self.fallback_reason: str | None = None

    def scrape(self) -> list[Course]:
        """
        Scrape all enrolled courses via the REST API.

        Returns:
            List[Course]: Enrolled courses for the selected term/level.
        """
        logger.info("Scraping enrolled courses...")
        self.fallback_reason = None

        courses: list[Course] = []
        try:
            all_sites: list = []
            limit = 50
            while True:
                data = self.session.get_json(
                    f"/direct/site.json?_limit={limit}&_start={len(all_sites)}"
                )
                sites = data.get("site_collection", [])
                if not sites:
                    break
                all_sites.extend(sites)
                if len(sites) < limit:
                    break

            for site in all_sites:
                course = self._parse_site(site)
                if course:
                    courses.append(course)
        except Exception as e:
            logger.error(f"Error scraping courses via REST API: {e}")

        if not courses:
            logger.info("Found 0 enrolled courses")
            return courses

        target = self._select_target_term(courses)

        if target:
            term_filtered = [c for c in courses if c.term == target]
            logger.info(
                f"Filtered to term '{target}': " f"{len(term_filtered)}/{len(courses)} courses"
            )
        else:
            term_filtered = courses
            logger.info("No parseable term token found; keeping all courses")

        final = self._apply_level_filter(term_filtered)

        if not final:
            if term_filtered:
                final = term_filtered
                self.fallback_reason = (
                    f"course level filter ({self.settings.course_level_filter}+) "
                    f"matched no courses for term {target or 'auto'}"
                )
            else:  # defensive: term selection keeps term_filtered non-empty
                final = courses
                self.fallback_reason = f"no courses matched term {target}"
            logger.warning(f"Filter would leave 0 courses; falling back ({self.fallback_reason})")

        logger.info(f"Found {len(final)} enrolled courses")
        return final

    def _select_target_term(self, courses: list[Course]) -> str | None:
        """
        Choose the term to filter on.

        A non-empty CURRENT_SEMESTER override is honored only if it matches at
        least one enrolled site; otherwise the latest term present in the sites
        is auto-detected. Returns the term token (e.g. "S2-2526") or None when
        no site carries a parseable term.
        """
        override = (self.settings.current_semester or "").strip()
        if override and override.lower() != "auto":
            override = override.upper()
            if any(c.term == override for c in courses):
                return override
            logger.warning(
                f"CURRENT_SEMESTER={override} not found among "
                f"{len(courses)} sites; auto-detecting latest term"
            )

        latest = latest_term(parse_term(c.title) for c in courses)
        return latest.raw if latest else None

    def _apply_level_filter(self, courses: list[Course]) -> list[Course]:
        """Filter to courses at or above the configured level (e.g. 300+)."""
        level_filter = self.settings.course_level_filter
        if not level_filter or not courses:
            return courses

        min_digit = str(level_filter)[0]  # e.g. 300 -> "3"
        filtered = [c for c in courses if self._course_meets_level(c.code, min_digit)]
        logger.info(
            f"Filtered to level {level_filter}+: " f"{len(filtered)}/{len(courses)} courses"
        )
        return filtered

    def _parse_site(self, site: dict) -> Course | None:
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
        parsed_term = parse_term(title)

        return Course(
            site_id=site_id,
            code=self.extract_course_code(title),
            title=title,
            url=url,
            term=parsed_term.raw if parsed_term else None,
        )

    @staticmethod
    def _course_meets_level(code: str, min_digit: str) -> bool:
        """
        Check if a course code meets the minimum level.

        Extracts the first digit of the course number and compares.
        E.g., code='CSCD 301', min_digit='3' -> True
             code='CSCD 201', min_digit='3' -> False
        """
        match = re.search(r"(\d)", code)
        if match:
            return match.group(1) >= min_digit
        return True  # Include if we can't determine level

    def get_course_by_code(self, code: str) -> Course | None:
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
