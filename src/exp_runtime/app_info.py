"""Public runtime identity, independent of the imported game's version."""
from importlib.metadata import PackageNotFoundError, version


PROJECT_REPOSITORY = 'joshrmcdaniel/exp-runtime'
PROJECT_URL = f'https://github.com/{PROJECT_REPOSITORY}'


def runtime_version():
    try:
        return version('exp-runtime')
    except PackageNotFoundError:
        return 'development'
