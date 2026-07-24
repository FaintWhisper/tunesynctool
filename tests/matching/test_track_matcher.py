import logging
from unittest.mock import MagicMock, patch

import pytest
from musicbrainzngs import MusicBrainzError

from tunesynctool.drivers import ServiceDriver
from tunesynctool.exceptions import TrackNotFoundException
from tunesynctool.features import TrackMatcher
from tunesynctool.models import MatchAssessment, MatchPolicy, Track


def build_target() -> MagicMock:
    target = MagicMock(spec=ServiceDriver)
    target.service_name = 'subsonic'
    target.supports_direct_isrc_querying = False
    target.supports_musicbrainz_id_querying = False
    return target


def test_same_service_missing_id_falls_back_to_text_search() -> None:
    source = Track(
        title="Exact title",
        album_name="Exact album",
        primary_artist="Exact artist",
        duration_seconds=180,
        service_id="unavailable-source-id",
        service_name="spotify",
    )
    text_match = Track(
        title=source.title,
        album_name=source.album_name,
        primary_artist=source.primary_artist,
        duration_seconds=source.duration_seconds,
        service_id="market-available-id",
        service_name="spotify",
    )
    target = MagicMock(spec=ServiceDriver)
    target.service_name = "spotify"
    target.supports_direct_isrc_querying = False
    target.supports_musicbrainz_id_querying = False
    target.get_track.side_effect = TrackNotFoundException("Unavailable")
    target.search_tracks.return_value = [text_match]

    result = TrackMatcher(target).find_match(source)

    assert result is text_match
    target.get_track.assert_called_once_with(source.service_id)
    assert target.search_tracks.called


def test_text_search_ranks_all_candidates_instead_of_returning_first() -> None:
    source = Track(
        title='Example Track',
        primary_artist='Primary Artist',
        duration_seconds=271,
        service_name='spotify',
    )
    earlier_but_worse = Track(
        title='Example Track',
        primary_artist='Primary Artist • Guest Artist',
        duration_seconds=279,
        service_id='worse',
        service_name='subsonic',
    )
    later_and_exact = Track(
        title='Example Track (feat. Guest Artist)',
        primary_artist='Primary Artist & Guest Artist',
        duration_seconds=271,
        service_id='exact',
        service_name='subsonic',
    )
    target = build_target()
    target.search_tracks.return_value = [earlier_but_worse, later_and_exact]

    result = TrackMatcher(target).find_match(source)

    assert result is later_and_exact


def test_text_search_rejects_earlier_wrong_version() -> None:
    source = Track(
        title='Example Track',
        primary_artist='Primary Artist',
        duration_seconds=208,
        service_name='spotify',
    )
    sped_up = Track(
        title='Example Track (Sped Up)',
        primary_artist='Primary Artist • Guest Artist',
        duration_seconds=184,
        service_id='sped-up',
        service_name='subsonic',
    )
    exact = Track(
        title='Example Track (feat. Guest Artist)',
        primary_artist='Primary Artist & Guest Artist',
        duration_seconds=208,
        service_id='exact',
        service_name='subsonic',
    )
    target = build_target()
    target.search_tracks.return_value = [sped_up, exact]

    assert TrackMatcher(target).find_match(source) is exact


def test_exact_version_label_wins_over_compatible_unlabelled_candidate() -> None:
    source = Track(
        title='Example Track - Radio Edit',
        primary_artist='Primary Artist',
        duration_seconds=180,
        service_name='spotify',
    )
    unlabelled = Track(
        title='Example Track',
        primary_artist='Primary Artist',
        duration_seconds=180,
        service_id='unlabelled',
        service_name='subsonic',
    )
    exact = Track(
        title='Example Track - Radio Edit',
        primary_artist='Primary Artist',
        duration_seconds=180,
        service_id='exact',
        service_name='subsonic',
    )
    target = build_target()

    assert TrackMatcher(target).select_best_candidate(
        source,
        [unlabelled, exact],
    ) is exact


def test_query_plan_preserves_symbols_and_uses_credited_artists() -> None:
    source = Track(
        title='+ (with Guest Artist)',
        primary_artist='Primary Artist',
        additional_artists=['Guest Collective'],
        service_name='spotify',
    )
    target = build_target()
    target.search_tracks.return_value = []

    assert TrackMatcher(target).find_match(source) is None

    queries = [
        call.kwargs['query']
        for call in target.search_tracks.call_args_list
    ]
    normalized_queries = [' '.join(query.casefold().split()) for query in queries]
    assert 'Primary Artist +' in queries
    assert '+' in queries
    assert 'Guest Artist +' in queries
    assert 'Guest Collective +' in queries
    assert len(normalized_queries) == len(set(normalized_queries))


def test_ambiguous_materially_different_candidates_cause_abstention() -> None:
    source = Track(
        title='Ambiguous Song',
        primary_artist='Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    first = Track(
        title='Ambiguous Song',
        primary_artist='Artist',
        duration_seconds=203,
        service_id='first',
        service_name='subsonic',
    )
    second = Track(
        title='Ambiguous Song',
        primary_artist='Artist',
        duration_seconds=206,
        service_id='second',
        service_name='subsonic',
    )
    target = build_target()

    matcher = TrackMatcher(target, minimum_margin=0.06)

    assert matcher.select_best_candidate(source, [first, second]) is None


def test_margin_considers_a_runner_up_just_below_acceptance_threshold() -> None:
    source = Track(
        title='Ambiguous Song',
        primary_artist='Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    best = Track(
        title='Ambiguous Song',
        primary_artist='Artist',
        duration_seconds=200,
        service_id='best',
        service_name='subsonic',
    )
    runner_up = Track(
        title='Ambiguous Song',
        primary_artist='Different Artist',
        duration_seconds=200,
        service_id='runner-up',
        service_name='subsonic',
    )
    assessments = {
        'best': MatchAssessment(
            score=0.836,
            accepted=True,
            policy=MatchPolicy.STRICT,
            title_similarity=1.0,
            artist_similarity=0.8,
            duration_similarity=0.8,
            album_similarity=None,
            track_number_similarity=None,
            year_similarity=None,
            evidence_coverage=0.95,
            version_compatible=True,
            authoritative=False,
            reasons=('recording evidence is compatible',),
        ),
        'runner-up': MatchAssessment(
            score=0.819,
            accepted=False,
            policy=MatchPolicy.STRICT,
            title_similarity=1.0,
            artist_similarity=0.8,
            duration_similarity=0.8,
            album_similarity=None,
            track_number_similarity=None,
            year_similarity=None,
            evidence_coverage=0.95,
            version_compatible=True,
            authoritative=False,
            reasons=('score is below threshold',),
        ),
    }
    source.evaluate_match = MagicMock(
        side_effect=lambda candidate, **_kwargs: assessments[candidate.service_id]
    )

    assert TrackMatcher(build_target()).select_best_candidate(
        source,
        [best, runner_up],
    ) is None


def test_duplicate_copies_do_not_create_false_ambiguity() -> None:
    source = Track(
        title='Duplicate Song',
        primary_artist='Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    first_copy = Track(
        title='Duplicate Song',
        primary_artist='Artist',
        duration_seconds=200,
        album_name='Album One',
        service_id='copy-1',
        service_name='subsonic',
    )
    second_copy = Track(
        title='Duplicate Song',
        primary_artist='Artist',
        duration_seconds=201,
        album_name='Album Two',
        service_id='copy-2',
        service_name='subsonic',
    )
    target = build_target()

    matcher = TrackMatcher(target, minimum_margin=1.0)

    assert matcher.select_best_candidate(
        source,
        [second_copy, first_copy],
    ) is first_copy


def test_same_service_id_is_deduplicated_despite_metadata_drift() -> None:
    source = Track(
        title='Duplicate Song',
        primary_artist='Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    first_copy = Track(
        title='Duplicate Song',
        primary_artist='Artist',
        duration_seconds=200,
        service_id='same-id',
        service_name='subsonic',
    )
    metadata_drift = Track(
        title='Duplicate Song (Producer Remix)',
        primary_artist='Artist',
        duration_seconds=200,
        service_id='same-id',
        service_name='subsonic',
    )
    matcher = TrackMatcher(build_target(), minimum_margin=1.0)

    assert matcher.select_best_candidate(
        source,
        [first_copy, metadata_drift],
    ) is first_copy
    assert matcher.select_best_candidate(
        source,
        [metadata_drift, first_copy],
    ) is first_copy


def test_candidates_without_service_ids_are_not_collapsed() -> None:
    source = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    unrelated = Track(
        title='Other Song',
        primary_artist='Other Artist',
        duration_seconds=200,
        service_name='subsonic',
    )
    wanted = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        service_name='subsonic',
    )
    target = build_target()

    assert TrackMatcher(target).select_best_candidate(
        source,
        [unrelated, wanted],
    ) is wanted


def test_idless_versions_are_distinct_and_selection_is_order_independent() -> None:
    source = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        album_name='Wanted Album',
        service_name='spotify',
    )
    canonical = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        album_name='Wanted Album',
        service_name='subsonic',
    )
    remix = Track(
        title='Wanted Song (Producer Remix)',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        album_name='Wanted Album',
        service_name='subsonic',
    )
    matcher = TrackMatcher(build_target())

    assert matcher.select_best_candidate(
        source,
        [remix, canonical],
    ) is canonical
    assert matcher.select_best_candidate(
        source,
        [canonical, remix],
    ) is canonical


def test_idless_scored_metadata_is_not_deduplicated_by_result_order() -> None:
    source = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        album_name='Wanted Album',
        track_number=1,
        release_year=2020,
        service_name='spotify',
    )
    exact = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        album_name='Wanted Album',
        track_number=1,
        release_year=2020,
        service_name='subsonic',
    )
    wrong_release = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        album_name='Wanted Album',
        track_number=9,
        release_year=1990,
        service_name='subsonic',
    )
    matcher = TrackMatcher(build_target())

    assert matcher.select_best_candidate(
        source,
        [wrong_release, exact],
    ) is exact
    assert matcher.select_best_candidate(
        source,
        [exact, wrong_release],
    ) is exact


def test_expected_musicbrainz_error_is_a_best_effort_miss(caplog) -> None:
    source = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    target = build_target()
    target.supports_musicbrainz_id_querying = True
    target.search_tracks.return_value = []

    with (
        patch(
            'tunesynctool.features.track_matcher.Musicbrainz.id_from_track',
            side_effect=MusicBrainzError('service unavailable'),
        ),
        caplog.at_level(
            logging.WARNING,
            logger='tunesynctool.features.track_matcher',
        ),
    ):
        result = TrackMatcher(target).find_match(source)

    assert result is None
    assert 'MusicBrainz enrichment failed' in caplog.records[-1].getMessage()


def test_unexpected_musicbrainz_error_is_not_silenced() -> None:
    source = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    target = build_target()
    target.supports_musicbrainz_id_querying = True
    target.search_tracks.return_value = []

    with (
        patch(
            'tunesynctool.features.track_matcher.Musicbrainz.id_from_track',
            side_effect=RuntimeError('implementation defect'),
        ),
        pytest.raises(RuntimeError, match='implementation defect'),
    ):
        TrackMatcher(target).find_match(source)


def test_rejected_top_candidate_logs_explainable_assessment(caplog) -> None:
    source = Track(
        title='Wanted Song',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    rejected = Track(
        title='Wanted Song (Instrumental)',
        primary_artist='Wanted Artist',
        duration_seconds=200,
        service_id='instrumental',
        service_name='subsonic',
    )
    assessment = MatchAssessment(
        score=0.71,
        accepted=False,
        policy=MatchPolicy.STRICT,
        title_similarity=1.0,
        artist_similarity=1.0,
        duration_similarity=1.0,
        album_similarity=None,
        track_number_similarity=None,
        year_similarity=None,
        evidence_coverage=0.95,
        version_compatible=False,
        authoritative=False,
        reasons=('incompatible recording version', 'score is below threshold'),
    )
    source.evaluate_match = MagicMock(return_value=assessment)

    with caplog.at_level(
        logging.DEBUG,
        logger='tunesynctool.features.track_matcher',
    ):
        result = TrackMatcher(build_target()).select_best_candidate(
            source,
            [rejected],
        )

    assert result is None
    message = caplog.records[-1].getMessage()
    assert 'Rejecting top match candidate' in message
    assert f'source={source}' in message
    assert f'candidate={rejected}' in message
    assert 'score=0.710' in message
    assert 'evidence_coverage=0.950' in message
    assert "('incompatible recording version', 'score is below threshold')" in message


def test_ambiguous_abstention_logs_top_candidate_evidence(caplog) -> None:
    source = Track(
        title='Ambiguous Song',
        primary_artist='Artist',
        duration_seconds=200,
        service_name='spotify',
    )
    best = Track(
        title='Ambiguous Song',
        primary_artist='Artist',
        duration_seconds=203,
        service_id='best',
        service_name='subsonic',
    )
    runner_up = Track(
        title='Ambiguous Song',
        primary_artist='Artist',
        duration_seconds=206,
        service_id='runner-up',
        service_name='subsonic',
    )

    with caplog.at_level(
        logging.DEBUG,
        logger='tunesynctool.features.track_matcher',
    ):
        result = TrackMatcher(
            build_target(),
            minimum_margin=0.06,
        ).select_best_candidate(source, [best, runner_up])

    assert result is None
    message = caplog.records[-1].getMessage()
    assert 'Abstaining from ambiguous match' in message
    assert f'source={source}' in message
    assert f'candidate={best}' in message
    assert 'score=' in message
    assert 'evidence_coverage=' in message
    assert 'reasons=' in message
    assert f'runner_up={runner_up}' in message
