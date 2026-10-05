"""Game registry; every game owns its asset and host-service contracts."""
from .shs import profile as shs
from .cod import profile as cod

GAMES = {profile.KEY: profile for profile in (shs, cod)}
SHS_ANDROID = 'shs-android-1.0.9'
SHS_IOS = 'shs-ios-assets-v1'
COD_IOS = 'cod-ios-assets-v1'
PROFILES = {name: (key, kind) for key, game in GAMES.items() for name, kind in game.PROFILES.items()}


def game_id(resources):
    library = getattr(resources, 'library', resources)
    return getattr(library, 'game_id', 'shs')

