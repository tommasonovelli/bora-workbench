"""Read metadata recorded in generated calibration evidence."""

from importlib.metadata import PackageNotFoundError, version


def launcher_version() -> str:
    """Read installed package metadata with the source-checkout development fallback."""
    try:
        return version("bora-workbench")
    except PackageNotFoundError:
        return "0.2.0"
