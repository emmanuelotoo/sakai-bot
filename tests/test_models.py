from sakai_bot.models import Course


def test_course_term_defaults_to_none():
    course = Course(site_id="s1", code="DCIT 306", title="DCIT 306 1 S2-2526", url="http://x")
    assert course.term is None


def test_course_accepts_term():
    course = Course(site_id="s1", code="DCIT 306", title="t", url="http://x", term="S2-2526")
    assert course.term == "S2-2526"
