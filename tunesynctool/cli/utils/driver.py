import tunesynctool.drivers as driver_module
from tunesynctool.drivers import ServiceDriver

DRIVER_CLASS_NAMES: dict[str, str] = {
    'spotify': 'SpotifyDriver',
    'spotify-public': 'SpotifyPublicDriver',
    'youtube': 'YouTubeDriver',
    'subsonic': 'SubsonicDriver',
    'deezer': 'DeezerDriver',
}

SUPPORTED_PROVIDERS = list(DRIVER_CLASS_NAMES.keys())
SOURCE_ONLY_PROVIDERS = {"deezer", "spotify-public"}
UNSAFE_SYNC_SOURCE_PROVIDERS = {"spotify-public"}


def get_driver_by_name(name: str) -> type[ServiceDriver]:
    """Get a driver class by its name."""

    return getattr(driver_module, DRIVER_CLASS_NAMES[name])
