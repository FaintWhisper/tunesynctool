from unittest.mock import patch

from tunesynctool.models import MatchPolicy, Track
from tunesynctool.utilities import parse_title


def make_track(
    title: str,
    artist: str,
    duration: int | None,
    *,
    album: str | None = None,
    year: int | None = None,
    track_number: int | None = None,
    additional_artists: list[str] | None = None,
) -> Track:
    return Track(
        title=title,
        primary_artist=artist,
        additional_artists=additional_artists or [],
        album_name=album,
        duration_seconds=duration,
        release_year=year,
        track_number=track_number,
        service_name='subsonic',
    )


def test_shared_feature_credit_cannot_override_different_base_title():
    source = make_track(
        'Cobalt (with Guest Artist)',
        'Primary Artist',
        212,
    )
    wrong_song = make_track(
        'Fugue (feat. Guest Artist)',
        'Primary Artist & Guest Artist',
        227,
    )

    assessment = source.evaluate_match(wrong_song)

    assert assessment.title_similarity < 0.2
    assert not assessment.accepted
    assert 'base title is not similar enough' in assessment.reasons


def test_soundtrack_suffix_and_artist_layout_match_exact_recording():
    source = make_track(
        'Example Theme (with Guest Artist) - From "Example Film: The Album"',
        'Primary Artist',
        232,
        additional_artists=['Guest Artist'],
    )
    candidate = make_track(
        'Example Theme',
        'Primary Artist • Guest Artist',
        232,
    )

    assert source.evaluate_match(candidate).accepted


def test_feature_layout_difference_is_safe_in_strict_mode():
    source = make_track('Example Track', 'Primary Artist', None)
    candidate = make_track(
        'Example Track (feat. Guest Artist)',
        'Primary Artist • Guest Artist',
        None,
    )

    assert source.evaluate_match(
        candidate,
        policy=MatchPolicy.STRICT,
    ).accepted


def test_duplicate_parenthetical_metadata_matches_in_strict_mode():
    source = make_track(
        'Example Title (Primary Artist Versus Guest Artist)',
        'Primary Artist',
        195,
        album='Example Album',
        additional_artists=['Guest Artist'],
    )
    candidate = make_track(
        'Example Title (Primary Artist Versus Guest Artist) '
        '(Primary Artist Versus Guest Artist)',
        'Primary Artist • Guest Artist',
        196,
        album='Example Album',
    )

    assert source.evaluate_match(
        candidate,
        policy=MatchPolicy.STRICT,
    ).accepted


def test_compound_version_and_credit_metadata_matches_in_strict_mode():
    source = make_track(
        'Example Single (Radio Edit) '
        '[feat. Guest Artist One and Guest Artist Two]',
        'Primary Artist',
        247,
        album='Example Single (Radio Edit)',
        additional_artists=['Guest Artist One', 'Guest Artist Two'],
    )
    candidate = make_track(
        'Example Single '
        '(Radio Edit - feat. Guest Artist One and Guest Artist Two)',
        'Primary Artist, Guest Artist One & Guest Artist Two',
        248,
        album=(
            'Example Single '
            '(Radio Edit - feat. Guest Artist One and Guest Artist Two)'
        ),
    )

    assert source.evaluate_match(
        candidate,
        policy=MatchPolicy.STRICT,
    ).accepted


def test_duration_is_strong_and_large_delta_is_a_hard_rejection():
    source = make_track('Example Track', 'Primary Artist', 332)
    remix = make_track(
        'Example Track (Guest Producer Remix)',
        'Primary Artist & Guest Producer',
        191,
    )

    assessment = source.evaluate_match(remix)

    assert assessment.score == 0.0
    assert not assessment.accepted
    assert any(reason.startswith('duration differs') for reason in assessment.reasons)


def test_relaxed_policy_rejects_unknown_named_version():
    source = make_track('Example Track', 'Primary Artist', 229)
    banda_version = make_track(
        'Example Track (banda Version)',
        'Primary Artist',
        229,
    )

    assert not source.evaluate_match(
        banda_version,
        policy=MatchPolicy.STRICT,
    ).accepted
    assessment = source.evaluate_match(
        banda_version,
        policy=MatchPolicy.RELAXED,
    )

    assert not assessment.accepted
    assert 'incompatible recording version' in assessment.reasons


def test_named_versions_require_the_same_qualifier():
    source = make_track('Song (banda Version)', 'Artist', 200)
    same_version = make_track('Song (banda Version)', 'Artist', 200)
    different_version = make_track('Song (salsa Version)', 'Artist', 200)

    assert source.evaluate_match(
        same_version,
        policy=MatchPolicy.RELAXED,
    ).accepted
    assessment = source.evaluate_match(
        different_version,
        policy=MatchPolicy.RELAXED,
    )

    assert not assessment.accepted
    assert 'different named recording versions' in assessment.reasons


def test_relaxed_policy_rejects_intro_version():
    source = make_track('Example Track', 'Primary Artist', 238)
    intro = make_track(
        'Example Track (Intro)',
        'Primary Artist & Guest Artist',
        219,
    )

    assert not source.evaluate_match(
        intro,
        policy=MatchPolicy.STRICT,
    ).accepted
    assessment = source.evaluate_match(
        intro,
        policy=MatchPolicy.RELAXED,
    )

    assert not assessment.accepted
    assert 'incompatible recording version' in assessment.reasons


def test_identically_labelled_intro_versions_match():
    source = make_track('Example Track (Intro)', 'Primary Artist', 219)
    candidate = make_track(
        'Example Track (Intro)',
        'Primary Artist & Guest Artist',
        219,
    )

    assert source.evaluate_match(
        candidate,
        policy=MatchPolicy.STRICT,
    ).accepted


def test_relaxed_policy_keeps_strict_duration_gate_for_unlabelled_copies():
    source = make_track(
        'Example Track (feat. Guest Artist)',
        'Primary Artist',
        189,
        additional_artists=['Guest Artist'],
    )
    longer_copy = make_track(
        'Example Track (feat. Guest Artist)',
        'Primary Artist & Guest Artist',
        204,
    )

    assert not source.evaluate_match(
        longer_copy,
        policy=MatchPolicy.STRICT,
    ).accepted
    assessment = source.evaluate_match(
        longer_copy,
        policy=MatchPolicy.RELAXED,
    )

    assert not assessment.accepted
    assert any(
        reason.startswith('duration differs')
        for reason in assessment.reasons
    )


def test_relaxed_policy_keeps_wider_gate_for_soft_label_difference():
    radio_edit = make_track('Example Track - Radio Edit', 'Artist', 180)
    unlabelled = make_track('Example Track', 'Artist', 185)

    assert not radio_edit.evaluate_match(
        unlabelled,
        policy=MatchPolicy.STRICT,
    ).accepted
    assert radio_edit.evaluate_match(
        unlabelled,
        policy=MatchPolicy.RELAXED,
    ).accepted


def test_year_is_only_a_weak_tie_breaker():
    source = make_track('Exact Song', 'Exact Artist', 200, year=2024)
    exact_duration_old_year = make_track(
        'Exact Song',
        'Exact Artist',
        200,
        year=1990,
    )
    worse_duration_same_year = make_track(
        'Exact Song',
        'Exact Artist',
        208,
        year=2024,
    )

    old_year = source.evaluate_match(exact_duration_old_year)
    same_year = source.evaluate_match(worse_duration_same_year)

    assert old_year.accepted
    assert same_year.accepted
    assert old_year.score > same_year.score
    assert old_year.year_similarity == 0.0


def test_missing_fields_are_excluded_instead_of_scored_as_equal_or_zero():
    source = make_track('Sparse Song', 'Sparse Artist', None)
    candidate = make_track('Sparse Song', 'Sparse Artist', None)

    assessment = source.evaluate_match(candidate)

    assert assessment.accepted
    assert assessment.album_similarity is None
    assert assessment.duration_similarity is None
    assert assessment.year_similarity is None
    assert assessment.evidence_coverage == 0.65


def test_one_generic_artist_word_does_not_create_a_match():
    source = make_track('Shared Title', 'The xx', 200)
    candidate = make_track('Shared Title', 'The Rolling Stones', 200)

    assert not source.evaluate_match(candidate).accepted


def test_same_service_identifier_is_authoritative():
    source = make_track('Old Metadata', 'Artist', 200)
    source.service_id = 'same-id'
    candidate = make_track('Updated Metadata', 'Different Credit', 230)
    candidate.service_id = 'same-id'

    assessment = source.evaluate_match(candidate)

    assert assessment.accepted
    assert assessment.authoritative


def test_title_only_candidate_is_not_enough_evidence():
    source = Track(
        title='Shared Title',
        primary_artist=None,
        duration_seconds=None,
        service_name='spotify',
    )
    candidate = Track(
        title='Shared Title',
        primary_artist=None,
        duration_seconds=None,
        service_name='subsonic',
    )

    assessment = source.evaluate_match(candidate)

    assert not assessment.accepted
    assert assessment.score == 0.0
    assert 'not enough corroborating metadata beyond the title' in assessment.reasons


def test_missing_titles_are_rejected_without_an_authoritative_identifier():
    source = Track(
        title=None,
        primary_artist='Same Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    candidate = Track(
        title=None,
        primary_artist='Same Artist',
        duration_seconds=200,
        service_name='subsonic',
    )

    assessment = source.evaluate_match(candidate)

    assert not assessment.accepted
    assert assessment.score == 0.0
    assert 'base title is missing' in assessment.reasons


def test_exact_version_label_scores_above_compatible_omitted_label():
    source = make_track('Song - Radio Edit', 'Artist', 180)
    exact = make_track('Song - Radio Edit', 'Artist', 180)
    omitted = make_track('Song', 'Artist', 180)

    exact_assessment = source.evaluate_match(exact)
    omitted_assessment = source.evaluate_match(omitted)

    assert exact_assessment.accepted
    assert omitted_assessment.accepted
    assert exact_assessment.score - omitted_assessment.score > 0.04


def test_titles_are_parsed_once_per_track_during_evaluation():
    source = make_track('Song - Radio Edit', 'Artist', 180)
    candidate = make_track('Song - Radio Edit', 'Artist', 180)

    with patch(
        'tunesynctool.models.track.parse_title',
        wraps=parse_title,
    ) as parser:
        assessment = source.evaluate_match(candidate)

    assert assessment.accepted
    assert parser.call_count == 2
