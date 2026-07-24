from typing import TYPE_CHECKING

from .spotify import SpotifyDriver
from .subsonic import SubsonicDriver
from .youtube import YouTubeDriver

if TYPE_CHECKING:
    from .deezer import DeezerDriver
    from .spotify_public import SpotifyPublicDriver

__all__ = ["SpotifyDriver", "SubsonicDriver", "YouTubeDriver"]


def __getattr__(name: str):
    if name == "DeezerDriver":
        from .deezer import DeezerDriver

        globals()[name] = DeezerDriver
        return DeezerDriver

    if name == "SpotifyPublicDriver":
        from .spotify_public import SpotifyPublicDriver

        globals()[name] = SpotifyPublicDriver
        return SpotifyPublicDriver

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
