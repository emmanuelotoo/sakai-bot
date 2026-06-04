from sakai_bot.scrapers.term import Term, latest_term, parse_term


def test_parse_term_extracts_token_from_title():
    assert parse_term("DCIT 306 1 S2-2526") == Term(year_code=2526, semester=2, raw="S2-2526")


def test_parse_term_is_case_insensitive_and_normalizes_raw():
    term = parse_term("dcit 306 1 s2-2526")
    assert term is not None
    assert term.raw == "S2-2526"


def test_parse_term_returns_none_when_absent():
    assert parse_term("DCIT 306 no term here") is None
    assert parse_term("") is None
    assert parse_term(None) is None


def test_parse_term_ignores_token_embedded_in_word():
    # A title like "PHYSICS3-2024" must not be misread as term S3-2024.
    assert parse_term("PHYSICS3-2024 Intro") is None


def test_term_ordering_newest_is_greatest():
    s1_2425 = parse_term("x S1-2425")
    s2_2425 = parse_term("x S2-2425")
    s1_2526 = parse_term("x S1-2526")
    s2_2526 = parse_term("x S2-2526")
    assert s1_2425 < s2_2425 < s1_2526 < s2_2526


def test_latest_term_picks_newest():
    terms = [parse_term("x S1-2526"), parse_term("x S2-2526"), parse_term("x S2-2425")]
    assert latest_term(terms).raw == "S2-2526"


def test_latest_term_empty_or_all_none_is_none():
    assert latest_term([]) is None
    assert latest_term([None]) is None
