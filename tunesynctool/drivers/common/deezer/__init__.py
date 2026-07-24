from typing import TYPE_CHECKING

from tunesynctool.exceptions import OptionalDependencyException

from .mapper import DeezerMapper

if TYPE_CHECKING:
    from .driver import DeezerDriver

_INSTALL_MESSAGE = (
    "Deezer support is not installed. Install this fork with the 'deezer' extra, "
    'for example: pip install "tunesynctool[deezer] @ '
    'git+https://github.com/FaintWhisper/tunesynctool.git"'
)

__all__ = ["DeezerMapper"]


def __getattr__(name: str):
    if name != "DeezerDriver":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    try:
        from .driver import DeezerDriver
    except ModuleNotFoundError as error:
        missing_root = error.name.split(".", 1)[0] if error.name else None
        if missing_root in {"streamrip", "deezer"}:
            raise OptionalDependencyException(_INSTALL_MESSAGE) from error
        raise

    globals()[name] = DeezerDriver
    return DeezerDriver
