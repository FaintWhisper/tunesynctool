from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable, Optional, Tuple


_DASH_TRANSLATION = str.maketrans({
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "―": "-",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "…": "...",
})

_CREDIT_CLAUSE = re.compile(
    r"^\s*(?:featuring|feat|ft|with)\.?\s+(.+?)\s*$",
    flags=re.IGNORECASE,
)
_INLINE_CREDIT = re.compile(
    r"\s+(?:featuring|feat|ft)\.?\s+(.+?)(?=\s+-\s+|$)",
    flags=re.IGNORECASE,
)
_COMPOUND_VERSION_CREDIT = re.compile(
    r"^\s*(.+?)\s+-\s+(?:featuring|feat|ft|with)\.?\s+(.+?)\s*$",
    flags=re.IGNORECASE,
)
_BRACKETED = re.compile(r"(\([^()]*\)|\[[^\[\]]*\])")
_DASH_SUFFIX = re.compile(r"\s+-\s+(.+?)\s*$")
_SOUNDTRACK_CONTEXT = re.compile(
    r"^\s*(?:from|music\s+from|from\s+the\s+(?:series|film|motion\s+picture))\b",
    flags=re.IGNORECASE,
)
_CREDIT_ARTIST_SEPARATOR = re.compile(
    r"\s*(?:[•·;,]|\s+&\s+|\s+\+\s+|\s+and\s+|\s+x\s+)\s*",
    flags=re.IGNORECASE,
)
_SERVICE_ARTIST_SEPARATOR = re.compile(r"\s*[•·]\s*")
_GENERIC_ARTIST_TOKENS = frozenset({"and", "the", "dj", "mc"})

_VERSION_PATTERNS = (
    ("sped_up", re.compile(r"\bsped[\s-]*up\b", re.IGNORECASE)),
    ("slowed", re.compile(r"\b(?:slowed|nightcore)\b", re.IGNORECASE)),
    ("instrumental", re.compile(r"\b(?:instrumental|karaoke)\b", re.IGNORECASE)),
    ("live", re.compile(r"\blive\b", re.IGNORECASE)),
    ("acoustic", re.compile(r"\bacoustic\b", re.IGNORECASE)),
    ("remaster", re.compile(r"\bremaster(?:ed)?\b", re.IGNORECASE)),
    ("radio", re.compile(r"\bradio\s+(?:edit|mix|version)\b", re.IGNORECASE)),
    ("club", re.compile(r"\bclub\s+(?:edit|mix|version)\b", re.IGNORECASE)),
    ("extended", re.compile(r"\bextended\s+(?:edit|mix|version)?\b", re.IGNORECASE)),
    ("vip", re.compile(r"\bvip(?:\s+mix)?\b", re.IGNORECASE)),
    ("cover", re.compile(r"\bcover(?:\s+version)?\b", re.IGNORECASE)),
    ("demo", re.compile(r"\bdemo\b", re.IGNORECASE)),
    ("clean", re.compile(r"\bclean(?:\s+version)?\b", re.IGNORECASE)),
    ("explicit", re.compile(r"\bexplicit(?:\s+version)?\b", re.IGNORECASE)),
    ("original", re.compile(r"\boriginal\s+(?:mix|version)\b", re.IGNORECASE)),
    ("intro", re.compile(r"\bintro\b", re.IGNORECASE)),
    ("remix", re.compile(r"\bremix\b", re.IGNORECASE)),
    ("edit", re.compile(r"\bedit\b", re.IGNORECASE)),
    ("mix", re.compile(r"\bmix\b", re.IGNORECASE)),
    ("version", re.compile(r"\bversion\b", re.IGNORECASE)),
)
_VERSION_QUALIFIER = re.compile(
    r"""
    ^\s*(?:
        sped[\s-]*up(?:\s+version)?
        |(?:slowed|nightcore)(?:\s+version)?
        |(?:instrumental|karaoke)(?:\s+(?:mix|version))?
        |live(?:\s+(?:at|from|in|on)\b.+)?
        |acoustic(?:\s+(?:mix|version))?
        |(?:\d{4}\s+)?remaster(?:ed)?(?:\s+\d{4})?
        |(?:radio|club|extended|original)\s+(?:edit|mix|version)
        |vip(?:\s+mix)?
        |cover(?:\s+version)?
        |demo(?:\s+version)?
        |(?:clean|explicit)(?:\s+version)?
        |(?:extended\s+)?intro(?:\s+(?:edit|mix|version))?
        |(?:.+?\s+)?remix
        |(?:.+?\s+)?edit
        |(?:.+?\s+)?mix
        |(?:.+?\s+)?version
    )\s*$
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class TitleParts:
    """Semantic pieces extracted from a display title."""

    base_title: str
    normalized_base_title: str
    featured_artists: Tuple[str, ...]
    version_tags: frozenset[str]
    version_qualifier: str


def _fold_unicode(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.translate(_DASH_TRANSLATION))
    return "".join(character for character in text if not unicodedata.combining(character))


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_text(value: Optional[str]) -> str:
    """Unicode-normalize text without removing meaningful words."""

    if not value:
        return ""

    text = _fold_unicode(value).casefold().strip()
    text = re.sub(r"(?<=\w)\s*[&+]\s*(?=\w)", " and ", text)
    text = re.sub(r"(?<=\s)[&+](?=\s)", " and ", text)
    text = text.replace("'", "")
    text = re.sub(r"[\[\](){}]", " ", text)
    text = re.sub(r"[/\\_.:,;!?\"|•·-]+", " ", text)
    text = re.sub(r"[^\w#+\s]", " ", text)
    return _normalize_whitespace(text)


def _version_tags(value: str) -> frozenset[str]:
    tags = {name for name, pattern in _VERSION_PATTERNS if pattern.search(value)}

    if "radio" in tags or "club" in tags or "extended" in tags:
        tags.discard("edit")
        tags.discard("mix")
        tags.discard("version")
    if "original" in tags:
        tags.discard("mix")
        tags.discard("version")
    if "instrumental" in tags:
        tags.discard("mix")
        tags.discard("version")
    if "remix" in tags:
        tags.discard("mix")
    if tags - {"mix", "version"}:
        tags.discard("mix")
        tags.discard("version")

    return frozenset(tags)


def _looks_like_version_qualifier(value: str) -> bool:
    """Require version annotations to look like a complete qualifier."""

    return bool(_VERSION_QUALIFIER.fullmatch(value))


def _split_credit_artists(value: str) -> Tuple[str, ...]:
    value = re.sub(
        r"([,;])\s*(?:and|&|\+)\s+",
        r"\1 ",
        value,
        flags=re.IGNORECASE,
    )
    entities = []
    for candidate in _CREDIT_ARTIST_SEPARATOR.split(value):
        normalized = _normalize_whitespace(candidate.strip(" .-_"))
        if normalized and normalized not in entities:
            entities.append(normalized)
    return tuple(entities)


def parse_title(value: Optional[str]) -> TitleParts:
    """Parse a title without conflating credits and recording versions."""

    raw = value or ""
    working = _fold_unicode(raw).strip()
    featured_artists = []
    version_tags = set()
    version_qualifiers = []
    previous_meaningful_bracket = None
    previous_bracket_end = None

    def replace_bracket(match: re.Match[str]) -> str:
        nonlocal previous_bracket_end
        nonlocal previous_meaningful_bracket
        content = match.group(0)[1:-1].strip()
        follows_previous_bracket = (
            previous_bracket_end is not None
            and not working[previous_bracket_end:match.start()].strip()
        )
        previous_bracket_end = match.end()

        credit_match = _CREDIT_CLAUSE.match(content)
        if credit_match:
            featured_artists.extend(_split_credit_artists(credit_match.group(1)))
            previous_meaningful_bracket = None
            return " "

        compound_match = _COMPOUND_VERSION_CREDIT.match(content)
        if compound_match and _looks_like_version_qualifier(
            compound_match.group(1)
        ):
            qualifier = compound_match.group(1).strip()
            version_tags.update(_version_tags(qualifier))
            version_qualifiers.append(normalize_text(qualifier))
            featured_artists.extend(
                _split_credit_artists(compound_match.group(2))
            )
            previous_meaningful_bracket = None
            return " "

        tags = (
            _version_tags(content)
            if _looks_like_version_qualifier(content)
            else frozenset()
        )
        if tags:
            version_tags.update(tags)
            version_qualifiers.append(normalize_text(content))
            previous_meaningful_bracket = None
            return " "

        if _SOUNDTRACK_CONTEXT.match(content):
            previous_meaningful_bracket = None
            return " "

        # Parentheses can be part of the real title. Keep their contents when
        # they are not a credit, version, or soundtrack annotation.
        normalized_content = normalize_text(content)
        if (
            follows_previous_bracket
            and normalized_content
            and normalized_content == previous_meaningful_bracket
        ):
            return " "
        previous_meaningful_bracket = normalized_content or None
        return f" {content} "

    working = _BRACKETED.sub(replace_bracket, working)

    inline_credit = _INLINE_CREDIT.search(working)
    if inline_credit:
        featured_artists.extend(_split_credit_artists(inline_credit.group(1)))
        working = f"{working[:inline_credit.start()]} {working[inline_credit.end():]}"

    while True:
        suffix_match = _DASH_SUFFIX.search(working)
        if not suffix_match:
            break

        suffix = suffix_match.group(1).strip()
        credit_match = _CREDIT_CLAUSE.match(suffix)
        tags = (
            _version_tags(suffix)
            if _looks_like_version_qualifier(suffix)
            else frozenset()
        )

        if credit_match:
            featured_artists.extend(_split_credit_artists(credit_match.group(1)))
        elif tags:
            version_tags.update(tags)
            version_qualifiers.append(normalize_text(suffix))
        elif not _SOUNDTRACK_CONTEXT.match(suffix):
            break

        working = working[:suffix_match.start()]

    base_title = _normalize_whitespace(working.strip(" -"))
    normalized_base = normalize_text(base_title)

    unique_featured = []
    for artist in featured_artists:
        if artist and artist not in unique_featured:
            unique_featured.append(artist)

    return TitleParts(
        base_title=base_title,
        normalized_base_title=normalized_base,
        featured_artists=tuple(unique_featured),
        version_tags=frozenset(version_tags),
        version_qualifier=" ".join(sorted(set(version_qualifiers))),
    )


def _artist_aliases(value: str) -> set[str]:
    normalized = normalize_text(value)
    if not normalized or normalized in _GENERIC_ARTIST_TOKENS:
        return set()

    aliases = {normalized}
    words = [word for word in normalized.split() if word not in _GENERIC_ARTIST_TOKENS]
    without_generic = " ".join(words)
    if without_generic:
        aliases.add(without_generic)

    return aliases


def artist_entities(
    primary_artist: Optional[str],
    additional_artists: Optional[Iterable[str]] = None,
    featured_artists: Optional[Iterable[str]] = None,
) -> frozenset[str]:
    """Return normalized artist entities and safe aliases."""

    structured_artists = [
        artist
        for artist in (
            *(additional_artists or ()),
            *(featured_artists or ()),
        )
        if artist
    ]

    entities = set()
    for artist in structured_artists:
        entities.update(_artist_aliases(artist))

    if primary_artist:
        entities.update(_artist_aliases(primary_artist))
        for part in _SERVICE_ARTIST_SEPARATOR.split(primary_artist):
            entities.update(_artist_aliases(part))

        # Ampersands, commas, "and", "x", and plus signs can belong to a
        # single artist's name. Split them only when structured metadata
        # independently confirms that the display value contains a credit.
        structured_names = {
            normalize_text(artist)
            for artist in structured_artists
            if normalize_text(artist)
        }
        ambiguous_parts = _split_credit_artists(primary_artist)
        if (
            len(ambiguous_parts) > 1
            and any(
                normalize_text(part) in structured_names
                for part in ambiguous_parts
            )
        ):
            for part in ambiguous_parts:
                entities.update(_artist_aliases(part))

    return frozenset(entities)
