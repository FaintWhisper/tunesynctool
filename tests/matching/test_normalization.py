from tunesynctool.utilities.normalization import (
    artist_entities,
    normalize_text,
    parse_title,
)

def test_normalize_text_folds_case_punctuation_and_spacing():
    assert normalize_text("  It's A—Test!  ") == 'its a test'
    assert normalize_text('Rock & Roll') == 'rock and roll'
    assert normalize_text(None) == ''


def test_standalone_plus_is_preserved():
    assert normalize_text('+') == '+'
    assert parse_title('+').normalized_base_title == '+'


def test_title_parser_removes_credits_and_soundtrack_context():
    parsed = parse_title(
        'Example Theme (with Guest Artist) - From "Example Film: The Album"'
    )

    assert parsed.normalized_base_title == 'example theme'
    assert parsed.featured_artists == ('Guest Artist',)
    assert parsed.version_tags == frozenset()


def test_title_parser_preserves_meaningful_parentheses():
    parsed = parse_title('Example Title (Meaningful Subtitle)')

    assert parsed.normalized_base_title == 'example title meaningful subtitle'


def test_title_parser_collapses_adjacent_duplicate_meaningful_parentheses():
    parsed = parse_title(
        'Example Title (Primary Artist Versus Guest Artist) '
        '(Primary Artist Versus Guest Artist)'
    )

    assert (
        parsed.normalized_base_title
        == 'example title primary artist versus guest artist'
    )


def test_title_parser_keeps_distinct_or_nonadjacent_parentheses():
    distinct = parse_title('Song (Part One) (Part Two)')
    nonadjacent = parse_title('Song (Part One) Reprise (Part One)')

    assert distinct.normalized_base_title == 'song part one part two'
    assert (
        nonadjacent.normalized_base_title
        == 'song part one reprise part one'
    )


def test_title_parser_separates_compound_version_and_credit_clause():
    parsed = parse_title(
        'Example Track '
        '(Radio Edit - feat. Guest Artist One and Guest Artist Two)'
    )

    assert parsed.normalized_base_title == 'example track'
    assert parsed.version_tags == frozenset({'radio'})
    assert parsed.version_qualifier == 'radio edit'
    assert parsed.featured_artists == (
        'Guest Artist One',
        'Guest Artist Two',
    )


def test_title_parser_keeps_nonversion_part_of_compound_credit_clause():
    parsed = parse_title('Example Track (Why - feat. Guest Artist)')

    assert parsed.normalized_base_title == 'example track why'
    assert parsed.version_tags == frozenset()
    assert parsed.featured_artists == ('Guest Artist',)


def test_title_parser_cleans_oxford_comma_artist_credits():
    parsed = parse_title(
        'Example Track (feat. Artist One, Artist Two, and Artist Three)'
    )

    assert parsed.featured_artists == (
        'Artist One',
        'Artist Two',
        'Artist Three',
    )
    entities = artist_entities(None, featured_artists=parsed.featured_artists)
    assert 'artist three' in entities


def test_title_parser_preserves_artist_name_starting_with_and():
    parsed = parse_title('Example Track (feat. And Example)')

    assert parsed.featured_artists == ('And Example',)


def test_title_parser_does_not_mistake_words_inside_real_titles_for_versions():
    live = parse_title('Example Track (This Is How We Live)')
    mix = parse_title('Example Track (A Mix of Ideas)')

    assert live.normalized_base_title == 'example track this is how we live'
    assert live.version_tags == frozenset()
    assert mix.normalized_base_title == 'example track a mix of ideas'
    assert mix.version_tags == frozenset()


def test_title_parser_classifies_recording_versions():
    assert parse_title('Example Track (Sped Up)').version_tags == frozenset({
        'sped_up',
    })
    assert parse_title('Example Track - Radio Edit').version_tags == frozenset({
        'radio',
    })
    assert parse_title('Example Track (Intro)').version_tags == frozenset({
        'intro',
    })
    assert parse_title('Example Track (Instrumental Mix)').version_tags == frozenset({
        'instrumental',
    })
    assert parse_title('Example Track - Original Mix').version_tags == frozenset({
        'original',
    })


def test_title_parser_does_not_overclassify_intro_or_version_words():
    intro = parse_title('Example Track (Intro to Chapter Two)')
    version = parse_title('Example Track (A Version of Events)')

    assert intro.normalized_base_title == 'example track intro to chapter two'
    assert intro.version_tags == frozenset()
    assert version.normalized_base_title == 'example track a version of events'
    assert version.version_tags == frozenset()


def test_artist_entities_include_structured_credits_without_acronyms():
    entities = artist_entities(
        'abc',
        ['Example Collective'],
        ['Alpha Beta Collective', 'Guest Artist'],
    )

    assert 'abc' in entities
    assert 'alpha beta collective' in entities
    assert 'example collective' in entities
    assert 'guest artist' in entities
    assert 'ec' not in entities
    assert 'abc' not in artist_entities('Alpha Beta Collective')


def test_unrelated_artist_names_with_same_initials_do_not_intersect():
    assert not (
        artist_entities('Alpha Beta')
        & artist_entities('Another Band')
    )


def test_ambiguous_name_separators_are_not_split():
    ampersand = artist_entities('Artist One & Artist Two')
    comma = artist_entities('Artist One, Artist Two')
    semicolon = artist_entities('Artist One; Artist Two')

    assert 'artist one' not in ampersand
    assert 'artist two' not in ampersand
    assert 'artist one' not in comma
    assert 'artist two' not in comma
    assert 'artist one' not in semicolon
    assert 'artist two' not in semicolon


def test_service_bullet_separator_is_split():
    entities = artist_entities('Artist One • Artist Two')

    assert 'artist one' in entities
    assert 'artist two' in entities


def test_structured_credit_allows_safe_ampersand_split():
    entities = artist_entities(
        'Primary Artist & Guest Artist',
        featured_artists=['Guest Artist'],
    )

    assert 'primary artist' in entities
    assert 'guest artist' in entities


def test_bare_generic_artist_labels_do_not_become_entities():
    assert artist_entities('DJ') == frozenset()
    assert artist_entities('The') == frozenset()
