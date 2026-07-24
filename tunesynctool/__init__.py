from typing import TYPE_CHECKING

from .models.configuration import Configuration

from .drivers import SubsonicDriver, SpotifyDriver, YouTubeDriver

from .models import MatchAssessment, MatchPolicy, Playlist, Track

from .features import TrackMatcher, PlaylistSynchronizer

if TYPE_CHECKING:
    from .drivers import DeezerDriver, SpotifyPublicDriver

__all__ = [
    "Configuration",
    "SubsonicDriver",
    "SpotifyDriver",
    "YouTubeDriver",
    "Playlist",
    "Track",
    "MatchAssessment",
    "MatchPolicy",
    "TrackMatcher",
    "PlaylistSynchronizer",
]


def __getattr__(name: str):
    if name in {"DeezerDriver", "SpotifyPublicDriver"}:
        from . import drivers

        driver = getattr(drivers, name)
        globals()[name] = driver
        return driver

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
