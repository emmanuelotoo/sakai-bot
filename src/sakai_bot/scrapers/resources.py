"""
Resource scraper for Sakai.

Uses the Sakai content REST API (/direct/content/site/<siteId>.json)
to detect files uploaded to each course's Resources tool.
"""

import logging
from datetime import datetime, timedelta, timezone

from sakai_bot.auth.sakai_session import SakaiSession
from sakai_bot.models import Course, Resource
from sakai_bot.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ResourceScraper(BaseScraper):
    """
    Scrapes files from the Resources tool of Sakai courses.

    Only files modified within the configured lookback window are
    returned, so a fresh deployment doesn't flood notifications with
    the whole semester's uploads. Folders and undated entries are skipped.
    """

    def __init__(self, session: SakaiSession):
        """Initialize resource scraper."""
        super().__init__(session)

    def scrape(self, courses: list[Course]) -> list[Resource]:
        """
        Scrape recent resources from all provided courses.

        Args:
            courses: List of courses to scrape

        Returns:
            List[Resource]: Recently modified files across all courses
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.resource_lookback_days)

        all_resources: list[Resource] = []
        seen_ids: set = set()

        for course in courses:
            try:
                resources = self._scrape_course_resources(course, cutoff)
                for res in resources:
                    if res.id not in seen_ids:
                        seen_ids.add(res.id)
                        all_resources.append(res)
                logger.debug(f"Found {len(resources)} recent resources in {course.code}")
            except Exception as e:
                logger.error(f"Error scraping resources for {course.code}: {e}")
                continue

        logger.info(f"Total recent resources scraped: {len(all_resources)}")
        return all_resources

    def _scrape_course_resources(self, course: Course, cutoff: datetime) -> list[Resource]:
        """
        Scrape recent resources for a single course via the REST API.

        Args:
            course: Course to scrape
            cutoff: Only include files modified after this time

        Returns:
            List[Resource]: Recent files from this course
        """
        try:
            data = self.session.get_json(f"/direct/content/site/{course.site_id}.json")
        except Exception as e:
            logger.debug(f"Could not get resources for {course.code}: {e}")
            return []

        resources: list[Resource] = []
        for item in self._walk_items(data.get("content_collection", [])):
            resource = self._parse_api_resource(item, course)
            if resource and resource.modified_at and resource.modified_at >= cutoff:
                resources.append(resource)

        return resources

    def _walk_items(self, items: list) -> list[dict]:
        """Flatten the content tree, recursing into nested children."""
        flat: list[dict] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            flat.append(item)
            children = item.get("resourceChildren") or item.get("children") or []
            if isinstance(children, list):
                flat.extend(self._walk_items(children))
        return flat

    def _parse_api_resource(self, item: dict, course: Course) -> Resource | None:
        """
        Parse a resource from the REST API response.

        Args:
            item: Content dict from API
            course: Course this belongs to

        Returns:
            Resource or None if the item is a folder or unparseable
        """
        if self._is_folder(item):
            return None

        res_id = item.get("resourceId") or item.get("id") or item.get("url")
        title = item.get("title") or item.get("name", "")

        if not res_id or not title:
            return None

        modified_at = self._parse_epoch_or_date(
            item.get("modifiedDate") or item.get("modified") or item.get("createdDate")
        )

        size_bytes = None
        try:
            size_bytes = int(item.get("size")) if item.get("size") is not None else None
        except (ValueError, TypeError):
            pass

        return Resource(
            id=str(res_id),
            course_code=course.code,
            course_title=course.title,
            title=str(title),
            container=item.get("container"),
            file_type=item.get("mimeType") or item.get("type"),
            size_bytes=size_bytes,
            modified_at=modified_at,
            author=item.get("author") or item.get("creator"),
            url=item.get("url"),
        )

    def _is_folder(self, item: dict) -> bool:
        """Check whether a content item is a folder rather than a file."""
        item_type = (item.get("type") or "").lower()
        mime_type = (item.get("mimeType") or "").lower()
        return (
            item_type == "collection" or "x-folder" in mime_type or item.get("isCollection") is True
        )

    def _parse_epoch_or_date(self, value) -> datetime | None:
        """Parse a date that could be epoch seconds/ms, an epoch dict, or a string."""
        if not value:
            return None

        if isinstance(value, dict):
            value = value.get("time") or value.get("epochSecond")
            if not value:
                return None

        if isinstance(value, (int, float)):
            try:
                # If > year 3000 in seconds, it's probably milliseconds
                if value > 32503680000:
                    value = value / 1000
                return datetime.fromtimestamp(value, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                return None

        if isinstance(value, str):
            if value.isdigit():
                return self._parse_epoch_or_date(int(value))
            return self.parse_date(value)

        return None
