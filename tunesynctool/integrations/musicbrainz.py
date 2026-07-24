import musicbrainzngs

from typing import Optional

from tunesynctool.models import Track
from tunesynctool.utilities import parse_title


musicbrainzngs.set_useragent(
    "tunesynctool",
    "1.0",
    "https://github.com/WilliamNT/tunesynctool",
)


class Musicbrainz:
    """Responsible for interacting with the MusicBrainz API."""

    @staticmethod
    def id_from_track(track: Track) -> Optional[str]:
        """
        Fetches the Musicbrainz ID for a track using its metadata.
        The less metadata, the less accurate the result.
        """
        response: dict = musicbrainzngs.search_recordings(
            query=parse_title(track.title).base_title or track.title,
            artist=track.primary_artist,
            date=track.release_year,
            alias=track.title,
            isrc=track.isrc,
        )

        return Musicbrainz.__get_id(response)

    @staticmethod
    def __get_id(data: dict) -> Optional[str]:
        items = data.get('recording-list', [])

        if not items:
            return None

        return items[0].get('id')
