from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from sakai_bot.models import Course
from sakai_bot.scrapers.resources import ResourceScraper

NOW_MS = int(datetime.now(timezone.utc).timestamp() * 1000)
OLD_MS = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp() * 1000)

COURSE = Course(
    site_id="site-1",
    code="DCIT 301",
    title="Operating Systems",
    url="https://sakai.example.com/portal/site/site-1",
)


def make_scraper(payload):
    session = Mock()
    session.get_json.return_value = payload
    session.base_url = "https://sakai.example.com"
    return ResourceScraper(session)


def test_recent_file_is_returned():
    scraper = make_scraper(
        {
            "content_collection": [
                {
                    "resourceId": "/group/site-1/slides.pdf",
                    "title": "Week 5 Slides",
                    "type": "resource",
                    "mimeType": "application/pdf",
                    "size": 12345,
                    "modifiedDate": NOW_MS,
                    "url": "https://sakai.example.com/access/content/group/site-1/slides.pdf",
                }
            ]
        }
    )

    resources = scraper.scrape([COURSE])

    assert len(resources) == 1
    res = resources[0]
    assert res.title == "Week 5 Slides"
    assert res.course_code == "DCIT 301"
    assert res.dedup_key == "resource:/group/site-1/slides.pdf"
    assert res.size_bytes == 12345


def test_old_files_are_filtered_out():
    scraper = make_scraper(
        {
            "content_collection": [
                {
                    "resourceId": "/group/site-1/old.pdf",
                    "title": "Old Handout",
                    "modifiedDate": OLD_MS,
                }
            ]
        }
    )
    assert scraper.scrape([COURSE]) == []


def test_folders_and_undated_items_are_skipped():
    scraper = make_scraper(
        {
            "content_collection": [
                {
                    "resourceId": "/group/site-1/folder/",
                    "title": "Lectures",
                    "type": "collection",
                    "modifiedDate": NOW_MS,
                },
                {
                    "resourceId": "/group/site-1/mystery.pdf",
                    "title": "No Date",
                    # no modifiedDate: age unknown, skip to avoid flooding
                },
            ]
        }
    )
    assert scraper.scrape([COURSE]) == []


def test_nested_children_are_walked():
    scraper = make_scraper(
        {
            "content_collection": [
                {
                    "resourceId": "/group/site-1/folder/",
                    "title": "Lectures",
                    "type": "collection",
                    "resourceChildren": [
                        {
                            "resourceId": "/group/site-1/folder/notes.docx",
                            "title": "Lecture Notes",
                            "modifiedDate": NOW_MS,
                        }
                    ],
                }
            ]
        }
    )

    resources = scraper.scrape([COURSE])
    assert [r.title for r in resources] == ["Lecture Notes"]


def test_api_failure_is_non_fatal():
    session = Mock()
    session.get_json.side_effect = RuntimeError("404")
    scraper = ResourceScraper(session)
    assert scraper.scrape([COURSE]) == []


def test_reupload_changes_content_hash():
    def payload(size):
        return {
            "content_collection": [
                {
                    "resourceId": "/group/site-1/slides.pdf",
                    "title": "Slides",
                    "size": size,
                    "modifiedDate": NOW_MS,
                }
            ]
        }

    first = make_scraper(payload(100)).scrape([COURSE])[0]
    second = make_scraper(payload(200)).scrape([COURSE])[0]
    assert first.dedup_key == second.dedup_key
    assert first.content_hash != second.content_hash


@pytest.mark.parametrize(
    "value,expected_none",
    [
        (None, True),
        ({"time": NOW_MS}, False),
        (str(NOW_MS), False),
        ("not a date at all %%%", True),
    ],
)
def test_parse_epoch_or_date_variants(value, expected_none):
    scraper = make_scraper({})
    result = scraper._parse_epoch_or_date(value)
    assert (result is None) == expected_none
