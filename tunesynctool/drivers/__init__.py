from typing import TYPE_CHECKING

from .service_driver import ServiceDriver
from .service_mapper import ServiceMapper

from .common import SpotifyDriver, SubsonicDriver, YouTubeDriver

if TYPE_CHECKING:
    from .common import DeezerDriver, SpotifyPublicDriver

__all__ = [
    "ServiceDriver",
    "ServiceMapper",
    "SpotifyDriver",
    "SubsonicDriver",
    "YouTubeDriver",
]


def __getattr__(name: str):
    if name in {"DeezerDriver", "SpotifyPublicDriver"}:
        from . import common

        driver = getattr(common, name)
        globals()[name] = driver
        return driver

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
