"""Public runtime identity, independent of the imported game's version."""
from importlib.metadata import PackageNotFoundError, version


PROJECT_URL = 'https://github.com/joshrmcdaniel/shs-runtime'


def runtime_version():
    try:
        return version('exp-runtime')
    except PackageNotFoundError:
        return 'development'
