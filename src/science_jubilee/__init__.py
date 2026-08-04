import sys

if sys.version_info[:2] >= (3, 8):
    # TODO: Import directly (no need for conditional) when `python_requires = >= 3.8`
    from importlib.metadata import PackageNotFoundError, version  # pragma: no cover
else:
    from importlib_metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Use the distribution name (project name in setup.cfg/pyproject.toml)
    # The import package is `science_jubilee`, while the dist name is `science-jubilee`.
    dist_name = "science-jubilee"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError

from science_jubilee.machine_session import MachineSession  # noqa: E402

__all__ = ["MachineSession", "__version__"]
