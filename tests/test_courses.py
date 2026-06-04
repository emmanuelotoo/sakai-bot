import urllib.parse as urlparse

from sakai_bot.scrapers.courses import CourseScraper


class StubSession:
    """Minimal stand-in for SakaiSession used by CourseScraper."""

    def __init__(self, sites, base_url="https://sakai.test"):
        self._sites = sites
        self.base_url = base_url

    def get_json(self, path):
        query = urlparse.parse_qs(urlparse.urlparse(path).query)
        start = int(query.get("_start", ["0"])[0])
        limit = int(query.get("_limit", ["50"])[0])
        return {"site_collection": self._sites[start : start + limit]}


def _site(site_id, title, type_="course"):
    return {"id": site_id, "title": title, "type": type_}


def _make_scraper(sites, *, current_semester=None, level_filter=None):
    scraper = CourseScraper(StubSession(sites))
    scraper.settings.current_semester = current_semester
    scraper.settings.course_level_filter = level_filter
    return scraper


def test_auto_detects_latest_term():
    sites = [
        _site("s1", "DCIT 306 1 S2-2526"),
        _site("s2", "DCIT 201 1 S1-2526"),  # older term, excluded
        _site("s3", "DCIT 410 1 S2-2526"),
    ]
    courses = _make_scraper(sites).scrape()
    assert {c.site_id for c in courses} == {"s1", "s3"}


def test_course_term_is_populated_from_title():
    courses = _make_scraper([_site("s1", "DCIT 306 1 S2-2526")]).scrape()
    assert courses[0].term == "S2-2526"


def test_stale_override_falls_back_to_auto_detect():
    sites = [_site("s1", "DCIT 306 1 S2-2526"), _site("s2", "DCIT 318 1 S2-2526")]
    scraper = _make_scraper(sites, current_semester="S1-2526")  # not present
    courses = scraper.scrape()
    assert {c.site_id for c in courses} == {"s1", "s2"}  # auto-detected S2-2526
    assert scraper.fallback_reason is None  # we still found courses


def test_valid_override_is_honored():
    sites = [_site("s1", "DCIT 306 1 S2-2526"), _site("s2", "DCIT 201 1 S1-2526")]
    courses = _make_scraper(sites, current_semester="S1-2526").scrape()
    assert {c.site_id for c in courses} == {"s2"}


def test_override_is_case_insensitive():
    sites = [_site("s1", "DCIT 201 1 S1-2526"), _site("s2", "DCIT 306 1 S2-2526")]
    courses = _make_scraper(sites, current_semester="s1-2526").scrape()
    assert {c.site_id for c in courses} == {"s1"}


def test_level_filter_emptying_falls_back_to_term_set():
    sites = [_site("s1", "DCIT 201 1 S2-2526"), _site("s2", "DCIT 210 1 S2-2526")]
    scraper = _make_scraper(sites, level_filter=300)  # no 300+ course
    courses = scraper.scrape()
    assert {c.site_id for c in courses} == {"s1", "s2"}  # fell back to term set
    assert scraper.fallback_reason is not None
    assert "level" in scraper.fallback_reason.lower()


def test_level_filter_keeps_matching_courses():
    sites = [_site("s1", "DCIT 201 1 S2-2526"), _site("s2", "DCIT 306 1 S2-2526")]
    scraper = _make_scraper(sites, level_filter=300)
    courses = scraper.scrape()
    assert {c.site_id for c in courses} == {"s2"}
    assert scraper.fallback_reason is None


def test_no_parseable_term_keeps_all_courses():
    sites = [_site("s1", "Project Space"), _site("s2", "Study Group")]
    scraper = _make_scraper(sites)
    courses = scraper.scrape()
    assert {c.site_id for c in courses} == {"s1", "s2"}
    assert scraper.fallback_reason is None


def test_special_sites_are_dropped():
    sites = [
        _site("~admin", "My Workspace", type_="myworkspace"),
        _site("!gateway", "Gateway"),
        _site("s1", "DCIT 306 1 S2-2526"),
    ]
    courses = _make_scraper(sites).scrape()
    assert {c.site_id for c in courses} == {"s1"}


def test_no_sites_returns_empty_without_fallback():
    scraper = _make_scraper([])
    courses = scraper.scrape()
    assert courses == []
    assert scraper.fallback_reason is None
