import logging
from typing import Iterable, List, Optional, Sequence, Tuple

from musicbrainzngs import MusicBrainzError

from tunesynctool.drivers import ServiceDriver
from tunesynctool.exceptions import TrackNotFoundException
from tunesynctool.integrations import Musicbrainz
from tunesynctool.models.track import MatchAssessment, MatchPolicy, Track
from tunesynctool.utilities import (
    artist_entities,
    calculate_str_similarity,
    normalize_text,
    parse_title,
)


logger = logging.getLogger(__name__)


class TrackMatcher:
    """Find the best compatible recording on a target service."""

    def __init__(
        self,
        target_driver: ServiceDriver,
        *,
        policy: MatchPolicy | str = MatchPolicy.STRICT,
        minimum_margin: Optional[float] = None,
    ) -> None:
        self._target = target_driver
        self._policy = MatchPolicy.coerce(policy)
        self._minimum_margin = (
            0.04 if self._policy is MatchPolicy.STRICT else 0.03
        ) if minimum_margin is None else minimum_margin

    def find_match(self, track: Track) -> Optional[Track]:
        """
        Find a compatible target recording.

        Authoritative service/ISRC/MusicBrainz identifiers are attempted
        first. Text candidates are collected, deduplicated, and ranked; the
        service's result order never decides the winner.
        """

        direct_match = self.__search_on_origin_service(track)
        if direct_match:
            return direct_match

        isrc_match = self.__search_by_isrc_only(track)
        if isrc_match:
            return isrc_match

        known_mbid_match = self.__search_with_musicbrainz_id(
            track,
            musicbrainz_id=track.musicbrainz_id,
        )
        if known_mbid_match:
            return known_mbid_match

        text_match = self.__search_with_text(track)
        if text_match:
            return text_match

        if not track.musicbrainz_id:
            discovered_mbid = self.__get_musicbrainz_id(track)
            return self.__search_with_musicbrainz_id(
                track,
                musicbrainz_id=discovered_mbid,
            )

        return None

    def select_best_candidate(
        self,
        reference_track: Track,
        candidates: Iterable[Track],
    ) -> Optional[Track]:
        """Select the highest-confidence candidate or abstain if ambiguous."""

        assessed_by_key = {}
        for candidate in candidates:
            if candidate is None:
                continue

            assessment = reference_track.evaluate_match(
                candidate,
                policy=self._policy,
            )
            stable_key = self.__stable_candidate_key(candidate)
            current = assessed_by_key.get(stable_key)
            if (
                current is None
                or self.__assessment_rank(candidate, assessment)
                > self.__assessment_rank(*current)
            ):
                assessed_by_key[stable_key] = (candidate, assessment)

        assessed: List[Tuple[Track, MatchAssessment]] = list(
            assessed_by_key.values()
        )
        if not assessed:
            return None

        assessed.sort(
            key=lambda item: (
                item[1].score,
                item[1].evidence_coverage,
                self.__stable_candidate_key(item[0]),
                self.__candidate_metadata_key(item[0]),
            ),
            reverse=True,
        )
        best_candidate, best_assessment = assessed[0]
        if not best_assessment.accepted:
            logger.debug(
                "Rejecting top match candidate: source=%s candidate=%s "
                "score=%.3f evidence_coverage=%.3f reasons=%s",
                reference_track,
                best_candidate,
                best_assessment.score,
                best_assessment.evidence_coverage,
                best_assessment.reasons,
            )
            return None

        materially_different_runner_up = None
        for candidate, assessment in assessed[1:]:
            if (
                assessment.score > 0
                and not self.__same_recording_copy(best_candidate, candidate)
            ):
                materially_different_runner_up = (candidate, assessment)
                break

        if materially_different_runner_up and not best_assessment.authoritative:
            _runner_up, runner_up_assessment = materially_different_runner_up
            if best_assessment.score - runner_up_assessment.score < self._minimum_margin:
                logger.debug(
                    "Abstaining from ambiguous match: source=%s candidate=%s "
                    "score=%.3f evidence_coverage=%.3f reasons=%s "
                    "runner_up=%s runner_up_score=%.3f",
                    reference_track,
                    best_candidate,
                    best_assessment.score,
                    best_assessment.evidence_coverage,
                    best_assessment.reasons,
                    _runner_up,
                    runner_up_assessment.score,
                )
                return None

        return best_candidate

    def __get_musicbrainz_id(self, track: Track) -> Optional[str]:
        if not self._target.supports_musicbrainz_id_querying:
            return None

        try:
            return Musicbrainz.id_from_track(track)
        except MusicBrainzError as error:
            logger.warning("MusicBrainz enrichment failed: %s", error)
            return None

    def __search_with_musicbrainz_id(
        self,
        track: Track,
        *,
        musicbrainz_id: Optional[str],
    ) -> Optional[Track]:
        if not musicbrainz_id or not self._target.supports_musicbrainz_id_querying:
            return None

        results = self._target.search_tracks(
            query=musicbrainz_id,
            limit=5,
        )
        return self.select_best_candidate(track, results)

    def __search_with_text(self, track: Track) -> Optional[Track]:
        candidate_pool: List[Track] = []
        queried = set()

        for tier in self.__query_plan(track):
            for query, limit in tier:
                query_key = self.__query_key(query)
                if not query_key or query_key in queried:
                    continue

                queried.add(query_key)
                candidate_pool.extend(
                    self._target.search_tracks(
                        query=query,
                        limit=limit,
                    )
                )

            best_candidate = self.select_best_candidate(track, candidate_pool)
            if best_candidate:
                assessment = track.evaluate_match(
                    best_candidate,
                    policy=self._policy,
                )
                if (
                    assessment.authoritative
                    or (
                        assessment.score >= 0.93
                        and assessment.evidence_coverage >= 0.8
                    )
                ):
                    return best_candidate

        return self.select_best_candidate(track, candidate_pool)

    def __query_plan(
        self,
        track: Track,
    ) -> Tuple[
        Tuple[Tuple[str, int], ...],
        Tuple[Tuple[str, int], ...],
        Tuple[Tuple[str, int], ...],
    ]:
        title = parse_title(track.title)
        base_title = title.base_title or track.title or ""
        normalized_base = title.normalized_base_title
        raw_title = (track.title or "").strip()
        raw_primary_artist = (track.primary_artist or "").strip()
        normalized_primary_artist = normalize_text(track.primary_artist)

        credited_artists = []
        for artist in (
            [raw_primary_artist]
            + list(track.additional_artists or [])
            + list(title.featured_artists)
        ):
            artist = (artist or "").strip()
            if artist and self.__query_key(artist) not in {
                self.__query_key(existing) for existing in credited_artists
            }:
                credited_artists.append(artist)

        specific_queries = []
        if raw_primary_artist and raw_title:
            specific_queries.extend([
                (f"{raw_primary_artist} {raw_title}", 30),
                (f"{raw_title} {raw_primary_artist}", 30),
            ])
        if raw_primary_artist and base_title:
            specific_queries.extend([
                (f"{raw_primary_artist} {base_title}", 30),
                (f"{base_title} {raw_primary_artist}", 30),
            ])
        if normalized_primary_artist and normalized_base:
            specific_queries.append(
                (f"{normalized_primary_artist} {normalized_base}", 30)
            )
        for artist in credited_artists:
            if base_title:
                specific_queries.extend([
                    (f"{artist} {base_title}", 30),
                    (f"{base_title} {artist}", 30),
                ])

        title_queries = []
        if raw_title:
            title_queries.append((raw_title, 50))
        if base_title:
            title_queries.append((base_title, 50))
        if normalized_base:
            title_queries.append((normalized_base, 50))
        if track.album_name and raw_primary_artist:
            title_queries.append(
                (f"{raw_primary_artist} {track.album_name}", 30)
            )

        broad_queries = []
        for artist in credited_artists:
            broad_queries.append((artist, 40))

        return (
            self.__deduplicate_queries(specific_queries),
            self.__deduplicate_queries(title_queries),
            self.__deduplicate_queries(broad_queries),
        )

    def __search_on_origin_service(self, track: Track) -> Optional[Track]:
        if not (
            track.service_id
            and track.service_name
            and self._target.service_name
            and track.service_name == self._target.service_name
        ):
            return None

        try:
            maybe_match = self._target.get_track(track.service_id)
        except TrackNotFoundException:
            return None

        return self.select_best_candidate(track, [maybe_match] if maybe_match else [])

    def __search_by_isrc_only(self, track: Track) -> Optional[Track]:
        if not track.isrc or not self._target.supports_direct_isrc_querying:
            return None

        try:
            likely_match = self._target.get_track_by_isrc(isrc=track.isrc)
        except TrackNotFoundException:
            return None

        return self.select_best_candidate(
            track,
            [likely_match] if likely_match else [],
        )

    @staticmethod
    def __query_key(query: str) -> str:
        return " ".join(query.casefold().split())

    @classmethod
    def __deduplicate_queries(
        cls,
        queries: Sequence[Tuple[str, int]],
    ) -> Tuple[Tuple[str, int], ...]:
        unique = []
        seen = set()
        for query, limit in queries:
            stripped = query.strip()
            key = cls.__query_key(stripped)
            if stripped and key not in seen:
                seen.add(key)
                unique.append((stripped, limit))
        return tuple(unique)

    @staticmethod
    def __stable_candidate_key(track: Track) -> Tuple[str, ...]:
        if track.service_id:
            return (
                "service-id",
                (track.service_name or "").casefold(),
                str(track.service_id),
            )

        title = parse_title(track.title)
        isrc = "".join(
            character
            for character in (track.isrc or "").casefold()
            if character.isalnum()
        )
        if isrc:
            return ("isrc", isrc)

        musicbrainz_id = "".join(
            character
            for character in (track.musicbrainz_id or "").casefold()
            if character.isalnum()
        )
        if musicbrainz_id:
            return ("musicbrainz-id", musicbrainz_id)

        artists = artist_entities(
            track.primary_artist,
            track.additional_artists,
            title.featured_artists,
        )
        return (
            "metadata",
            (track.service_name or "").casefold(),
            title.normalized_base_title,
            "|".join(sorted(title.version_tags)),
            title.version_qualifier,
            "|".join(sorted(artists)),
            str(track.duration_seconds or ""),
            normalize_text(track.album_name),
            str(track.track_number or ""),
            str(track.release_year or ""),
        )

    @staticmethod
    def __candidate_metadata_key(track: Track) -> Tuple[str, ...]:
        return (
            normalize_text(track.title),
            normalize_text(track.primary_artist),
            "|".join(
                sorted(
                    normalize_text(artist)
                    for artist in (track.additional_artists or ())
                )
            ),
            normalize_text(track.album_name),
            str(track.duration_seconds or ""),
            str(track.track_number or ""),
            str(track.release_year or ""),
            (track.isrc or "").casefold(),
            (track.musicbrainz_id or "").casefold(),
        )

    @classmethod
    def __assessment_rank(
        cls,
        candidate: Track,
        assessment: MatchAssessment,
    ) -> Tuple[float, float, Tuple[str, ...]]:
        return (
            assessment.score,
            assessment.evidence_coverage,
            cls.__candidate_metadata_key(candidate),
        )

    @staticmethod
    def __same_recording_copy(left: Track, right: Track) -> bool:
        left_title = parse_title(left.title)
        right_title = parse_title(right.title)
        if left_title.normalized_base_title != right_title.normalized_base_title:
            return False
        if left_title.version_tags != right_title.version_tags:
            return False
        if (
            left_title.version_qualifier
            and right_title.version_qualifier
            and calculate_str_similarity(
                left_title.version_qualifier,
                right_title.version_qualifier,
            ) < 0.9
        ):
            return False

        left_artists = artist_entities(
            left.primary_artist,
            left.additional_artists,
            left_title.featured_artists,
        )
        right_artists = artist_entities(
            right.primary_artist,
            right.additional_artists,
            right_title.featured_artists,
        )
        if left_artists and right_artists and not (left_artists & right_artists):
            return False

        if left.duration_seconds and right.duration_seconds:
            return abs(left.duration_seconds - right.duration_seconds) <= 2

        return True
