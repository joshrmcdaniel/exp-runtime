"""Android 1.0.9 music cues from SHS09SoundEngine.playMusic in classes.dex.

The inspected iOS SHSSoundManager constructor uses the same cue table
(00074d74..000754ac); see docs/IPA.md for source availability limits.
Some script IDs name positions within another MP3, not separate assets.
Resolve them only for music playback; resource lookup and VM IDs stay exact.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MusicCue:
    asset_id: int
    start_ms: int = 0


_MUSIC_REDIRECTS = {
    8202: MusicCue(8201, 2800),
    8204: MusicCue(8203, 720),
    8206: MusicCue(8205, 28280),
    8208: MusicCue(8207, 3270),
    8211: MusicCue(8210, 6000),
    8213: MusicCue(8212, 4000),
    8214: MusicCue(8212, 39200),
    8216: MusicCue(8215, 1320),
    8218: MusicCue(8217, 1920),
    8220: MusicCue(8219, 10600),
    8225: MusicCue(8224, 29200),
}


def music_cue(resource_id: int) -> MusicCue:
    return _MUSIC_REDIRECTS.get(resource_id, MusicCue(resource_id))
