"""Read metadata recorded in generated calibration evidence."""

from importlib.metadata import PackageNotFoundError, version


def launcher_version() -> str:
    """Read installed package metadata with the source-checkout development fallback."""
    try:
        return version("qwen-launcher")
    except PackageNotFoundError:
        return "0.1.0rc1"
