from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Self, Tuple

from tunesynctool.utilities import (
    TitleParts,
    artist_entities,
    calculate_duration_similarity,
    calculate_str_similarity,
    calculate_year_similarity,
    normalize_text,
    parse_title,
)


class MatchPolicy(str, Enum):
    """How strictly two recordings must agree."""

    STRICT = "strict"
    RELAXED = "relaxed"

    @classmethod
    def coerce(cls, value: "MatchPolicy | str") -> "MatchPolicy":
        if isinstance(value, cls):
            return value
        return cls(value)


@dataclass(frozen=True)
class MatchAssessment:
    """Explainable result of comparing two tracks."""

    score: float
    accepted: bool
    policy: MatchPolicy
    title_similarity: float
    artist_similarity: Optional[float]
    duration_similarity: Optional[float]
    album_similarity: Optional[float]
    track_number_similarity: Optional[float]
    year_similarity: Optional[float]
    evidence_coverage: float
    version_compatible: bool
    authoritative: bool
    reasons: Tuple[str, ...]


_EVIDENCE_WEIGHTS = {
    "title": 0.38,
    "artist": 0.27,
    "duration": 0.30,
    "album": 0.03,
    "track_number": 0.01,
    "year": 0.01,
}
_DEFAULT_THRESHOLDS = {
    MatchPolicy.STRICT: 0.82,
    MatchPolicy.RELAXED: 0.78,
}
_NEUTRAL_VERSION_TAGS = frozenset({"original"})
_SOFT_VERSION_TAGS = frozenset({"radio", "edit", "clean", "explicit"})
_DANGEROUS_VERSION_TAGS = frozenset({
    "acoustic",
    "club",
    "cover",
    "demo",
    "extended",
    "instrumental",
    "intro",
    "live",
    "mix",
    "remaster",
    "remix",
    "slowed",
    "sped_up",
    "version",
    "vip",
})


def _normalized_identifier(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = "".join(character for character in value.casefold() if character.isalnum())
    return normalized or None


def _artist_similarity(
    source: "Track",
    candidate: "Track",
    source_title: TitleParts,
    candidate_title: TitleParts,
) -> Optional[float]:
    source_entities = artist_entities(
        source.primary_artist,
        source.additional_artists,
        source_title.featured_artists,
    )
    candidate_entities = artist_entities(
        candidate.primary_artist,
        candidate.additional_artists,
        candidate_title.featured_artists,
    )

    if not source_entities or not candidate_entities:
        return None
    if source_entities & candidate_entities:
        return 1.0

    return max(
        calculate_str_similarity(source_artist, candidate_artist)
        for source_artist in source_entities
        for candidate_artist in candidate_entities
    )


def _duration_gate(
    source: "Track",
    candidate: "Track",
    policy: MatchPolicy,
    source_title: TitleParts,
    candidate_title: TitleParts,
) -> float:
    longer_duration = max(source.duration_seconds or 0, candidate.duration_seconds or 0)
    includes_youtube = "youtube" in {
        (source.service_name or "").casefold(),
        (candidate.service_name or "").casefold(),
    }

    if includes_youtube:
        if policy is MatchPolicy.STRICT:
            return max(30.0, 0.15 * longer_duration)
        return max(45.0, 0.25 * longer_duration)

    if policy is MatchPolicy.RELAXED:
        source_tags = source_title.version_tags - _NEUTRAL_VERSION_TAGS
        candidate_tags = candidate_title.version_tags - _NEUTRAL_VERSION_TAGS
        differing_tags = source_tags ^ candidate_tags
        if differing_tags and differing_tags <= _SOFT_VERSION_TAGS:
            return max(20.0, 0.10 * longer_duration)

    # Unlabelled copies and equally labelled versions should not receive a
    # wider duration allowance merely because relaxed mode was selected.
    return max(10.0, 0.05 * longer_duration)


def _version_compatibility(
    source: "Track",
    candidate: "Track",
    policy: MatchPolicy,
    source_parts: TitleParts,
    candidate_parts: TitleParts,
) -> Tuple[bool, float, Optional[str]]:
    source_tags = source_parts.version_tags - _NEUTRAL_VERSION_TAGS
    candidate_tags = candidate_parts.version_tags - _NEUTRAL_VERSION_TAGS

    duration_delta = None
    if source.duration_seconds and candidate.duration_seconds:
        duration_delta = abs(source.duration_seconds - candidate.duration_seconds)

    if source_tags == candidate_tags:
        dangerous_tags = source_tags & _DANGEROUS_VERSION_TAGS
        source_qualifier = source_parts.version_qualifier
        candidate_qualifier = candidate_parts.version_qualifier
        if dangerous_tags and source_qualifier and candidate_qualifier:
            if (
                "version" in dangerous_tags
                and source_qualifier != candidate_qualifier
            ):
                return False, 0.0, "different named recording versions"
            qualifier_similarity = calculate_str_similarity(
                source_qualifier,
                candidate_qualifier,
            )
            if qualifier_similarity < 0.75:
                return False, 0.0, "different named recording versions"
        return True, 1.0, None

    differing_tags = source_tags ^ candidate_tags
    if (
        differing_tags
        and differing_tags <= _SOFT_VERSION_TAGS
        and duration_delta is not None
        and duration_delta <= 3
    ):
        return True, 0.85, "version label omitted but duration is effectively exact"

    if policy is MatchPolicy.RELAXED:
        if (source_tags | candidate_tags) & _DANGEROUS_VERSION_TAGS:
            return False, 0.0, "incompatible recording version"
        return True, 0.65, "relaxed policy accepted a soft version difference"

    return False, 0.0, "incompatible recording version"


@dataclass
class Track:
    """Represents a single track."""

    title: str = field(default=None)
    """Title of the track."""

    album_name: Optional[str] = field(default=None)
    """Name of the album containing the track."""

    primary_artist: Optional[str] = field(default=None)
    """Primary (album) artist for the track."""

    additional_artists: List[str] = field(default_factory=list)
    """Additional artist names for the track."""

    duration_seconds: Optional[int] = field(default=None)
    """Duration of the track in seconds."""

    track_number: Optional[int] = field(default=None)
    """Track number on the album."""

    release_year: Optional[int] = field(default=None)
    """Year the track was released."""

    isrc: Optional[str] = field(default=None)
    """International Standard Recording Code for the track."""

    musicbrainz_id: Optional[str] = field(default=None)
    """MusicBrainz ID for the track."""

    service_id: Optional[str] = field(default=None)
    """Source-service specific ID for the track."""

    service_name: str = field(default="unknown")
    """Source service for the track."""

    service_data: Optional[dict] = field(default_factory=dict)
    """Raw JSON response data from the source service."""

    def __str__(self) -> str:
        return f"{self.track_number}. - {self.primary_artist} - {self.title}"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: Optional[Self]) -> bool:
        if not other:
            return False
        if self.service_id is None or other.service_id is None:
            return self is other
        return self.service_id == other.service_id and self.service_name == other.service_name

    def __hash__(self):
        if self.service_id is None:
            return id(self)
        return hash((self.service_id, self.service_name))

    def evaluate_match(
        self,
        other: Optional[Self],
        *,
        policy: MatchPolicy | str = MatchPolicy.STRICT,
    ) -> MatchAssessment:
        """Evaluate another track using recording-aware, missing-aware evidence."""

        selected_policy = MatchPolicy.coerce(policy)
        minimum_score = _DEFAULT_THRESHOLDS[selected_policy]

        if not other:
            return MatchAssessment(
                score=0.0,
                accepted=False,
                policy=selected_policy,
                title_similarity=0.0,
                artist_similarity=None,
                duration_similarity=None,
                album_similarity=None,
                track_number_similarity=None,
                year_similarity=None,
                evidence_coverage=0.0,
                version_compatible=False,
                authoritative=False,
                reasons=("candidate is missing",),
            )

        same_service_id = (
            bool(self.service_id)
            and bool(other.service_id)
            and self.service_name == other.service_name
            and self.service_id == other.service_id
        )
        source_isrc = _normalized_identifier(self.isrc)
        candidate_isrc = _normalized_identifier(other.isrc)
        source_mbid = _normalized_identifier(self.musicbrainz_id)
        candidate_mbid = _normalized_identifier(other.musicbrainz_id)

        if same_service_id or (
            source_isrc and candidate_isrc and source_isrc == candidate_isrc
        ) or (
            source_mbid and candidate_mbid and source_mbid == candidate_mbid
        ):
            return MatchAssessment(
                score=1.0,
                accepted=True,
                policy=selected_policy,
                title_similarity=1.0,
                artist_similarity=1.0,
                duration_similarity=1.0,
                album_similarity=None,
                track_number_similarity=None,
                year_similarity=None,
                evidence_coverage=1.0,
                version_compatible=True,
                authoritative=True,
                reasons=("authoritative identifier match",),
            )

        reasons = []
        hard_rejection = False
        if (
            selected_policy is MatchPolicy.STRICT
            and source_isrc
            and candidate_isrc
            and source_isrc != candidate_isrc
        ):
            hard_rejection = True
            reasons.append("conflicting ISRC values")
        if (
            selected_policy is MatchPolicy.STRICT
            and source_mbid
            and candidate_mbid
            and source_mbid != candidate_mbid
        ):
            hard_rejection = True
            reasons.append("conflicting MusicBrainz recording IDs")

        source_title = parse_title(self.title)
        candidate_title = parse_title(other.title)
        titles_available = bool(
            source_title.normalized_base_title
            and candidate_title.normalized_base_title
        )
        title_similarity = (
            calculate_str_similarity(
                source_title.normalized_base_title,
                candidate_title.normalized_base_title,
            )
            if titles_available
            else 0.0
        )
        artist_similarity = _artist_similarity(
            self,
            other,
            source_title,
            candidate_title,
        )

        if not titles_available:
            hard_rejection = True
            reasons.append("base title is missing")
        else:
            minimum_title_similarity = (
                0.78 if selected_policy is MatchPolicy.STRICT else 0.72
            )
            shortest_title_length = min(
                len(source_title.normalized_base_title),
                len(candidate_title.normalized_base_title),
            )
            if shortest_title_length <= 3:
                minimum_title_similarity = 1.0
            if title_similarity < minimum_title_similarity:
                hard_rejection = True
                reasons.append("base title is not similar enough")

        minimum_artist_similarity = (
            0.62 if selected_policy is MatchPolicy.STRICT else 0.55
        )
        if artist_similarity is not None and artist_similarity < minimum_artist_similarity:
            hard_rejection = True
            reasons.append("credited artists are not similar enough")

        version_compatible, version_score, version_reason = _version_compatibility(
            self,
            other,
            selected_policy,
            source_title,
            candidate_title,
        )
        if not version_compatible:
            hard_rejection = True
        if version_reason:
            reasons.append(version_reason)

        duration_similarity = None
        if self.duration_seconds and other.duration_seconds:
            duration_gate = _duration_gate(
                self,
                other,
                selected_policy,
                source_title,
                candidate_title,
            )
            duration_delta = abs(self.duration_seconds - other.duration_seconds)
            duration_similarity = calculate_duration_similarity(
                self.duration_seconds,
                other.duration_seconds,
                duration_gate,
            )
            if duration_delta > duration_gate:
                hard_rejection = True
                reasons.append(
                    f"duration differs by {duration_delta}s "
                    f"(maximum {duration_gate:.1f}s)"
                )

        album_similarity = None
        if self.album_name and other.album_name:
            album_similarity = calculate_str_similarity(
                normalize_text(self.album_name),
                normalize_text(other.album_name),
            )

        track_number_similarity = None
        if (
            self.track_number is not None
            and other.track_number is not None
            and album_similarity is not None
            and album_similarity >= 0.8
        ):
            track_number_similarity = (
                1.0 if self.track_number == other.track_number else 0.0
            )

        year_similarity = calculate_year_similarity(
            self.release_year,
            other.release_year,
        )

        components: Dict[str, Optional[float]] = {
            # A compatible but omitted/soft version label remains matchable,
            # while an explicitly matching label wins candidate ranking.
            "title": title_similarity * version_score,
            "artist": artist_similarity,
            "duration": duration_similarity,
            "album": album_similarity,
            "track_number": track_number_similarity,
            "year": year_similarity,
        }
        available_weight = sum(
            _EVIDENCE_WEIGHTS[name]
            for name, value in components.items()
            if value is not None
        )
        minimum_evidence_coverage = 0.65
        if available_weight < minimum_evidence_coverage:
            hard_rejection = True
            reasons.append(
                "not enough corroborating metadata beyond the title"
            )
        weighted_score = sum(
            _EVIDENCE_WEIGHTS[name] * value
            for name, value in components.items()
            if value is not None
        )
        raw_score = weighted_score / available_weight if available_weight else 0.0
        score = 0.0 if hard_rejection else raw_score
        accepted = not hard_rejection and score >= minimum_score

        if not accepted and not hard_rejection:
            reasons.append(
                f"score {score:.3f} is below required {minimum_score:.3f}"
            )
        if accepted and not reasons:
            reasons.append("recording evidence is compatible")

        return MatchAssessment(
            score=score,
            accepted=accepted,
            policy=selected_policy,
            title_similarity=title_similarity,
            artist_similarity=artist_similarity,
            duration_similarity=duration_similarity,
            album_similarity=album_similarity,
            track_number_similarity=track_number_similarity,
            year_similarity=year_similarity,
            evidence_coverage=available_weight,
            version_compatible=version_compatible,
            authoritative=False,
            reasons=tuple(reasons),
        )
