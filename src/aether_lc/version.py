from importlib.metadata import PackageNotFoundError, version


PACKAGE_NAME = "aether-lc"


def get_version() -> str:
    """Return the installed distribution version."""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "unknown"
