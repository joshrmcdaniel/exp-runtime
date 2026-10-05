# SHS IPA assets

The desktop runtime can import a player-supplied SHS IPA instead of the Android
APK. Choose **Choose Game** during setup, drop the IPA onto the setup window,
or run:

```sh
uv run --locked shs-tool import --ipa /path/to/game.ipa --library /path/to/ios-library
```

Add `--episodes /path/to/Episodes` for additional EXP files. The game package
and episodes are retained privately in the library. Nothing is downloaded,
and no original artwork, fonts, scripts or executable is distributed with the
engine. This adds an asset source to the desktop player; it does not build an
iOS application or execute the original Mach-O binary.

Episode title language can be selected in Options. The supplied IPA has one
English game string bank and no alternate translated story scripts were found.
Its root `Localizable.strings` translates an EA Mobile promotional message
into seven languages, not story or menu text. See the
[localization inspection](MAIN_MENU.md#episode-title-languages) for native
addresses and the title-selection limits.

## Optional APK music

Some original iOS music was downloaded separately and is absent from the IPA.
To supply it locally, add an optional Android 1.0.9 APK:

```sh
uv run --locked shs-tool import --ipa /path/to/game.ipa --music-apk /path/to/game.apk --library /path/to/ios-library
```

For an existing IPA library, choose **Options → Content Library → Add APK
Music**, drop one APK onto the menu, or run:

```sh
uv run --locked shs-tool add-music --apk /path/to/game.apk --library /path/to/ios-library
```

During first setup, dropping one IPA and one APK together also selects the IPA
as the game and the APK as the music source. Additional EXP files may accompany
that initial drop. When adding music to an existing library, add the APK and
any episode files in separate operations.

**IPA assets always take precedence.** The supplement exposes only missing
members of the ten verified music IDs listed below, using their exact Android
`assets/Assets/audio/music/<id>.mp3` paths. Android artwork, fonts, scripts and
bundled episodes are not substituted or imported. Font selection remains the
bundled/installed original face, followed by the system default. Other missing
assets keep their existing errors rather than acquiring guessed mappings.

The APK is copied privately into the library, validated against the existing
Android 1.0.9 native profile, and checked for every needed track before the
manifest is replaced. Duplicate members, missing tracks, invalid profiles and
ZIP errors abort the operation. Repeating an import after all ten tracks are
available does nothing. The original inputs can be moved or removed afterward.
No game files are downloaded or included in the engine distribution.

Existing IPA saves continue to load. Music import leaves their bytes, episode
IDs, script state and font metrics unchanged. A live story retries a previously
missing cue when resumed; an already loaded stream keeps its paused position.

## Identification and compatibility

The importer requires one `Payload/<name>.app/Info.plist` and recognizes SHS
by `CFBundleIdentifier`: `com.ea.shs`, optionally followed by regional/product
suffixes separated by dots. The inspected package uses `com.ea.shs.row`.
An unrelated bundle identifier is rejected even if its files have similar names.

**Version numbers are informational.** Neither the displayed version, build
number, executable name nor executable hash gates import. Compatibility is
checked against the required assets in `res_generated/`: supported payload
formats, UI string/layout ranges, image frames, portrait-mask dimensions,
sprite atlases and glyph-font records. Malformed or missing required resources
produce an error naming the asset. Duplicate ZIP members, ambiguous app roots
and malformed plists are rejected. Binary and XML plists are supported.

The implementation was exercised with the supplied IPA reporting version
`1.4.2`, build `1.4.3.54`. Other versions with this asset contract may import;
this is not a claim that every SHS release has the same bytecode or services.
Episode-specific graphics and audio are checked when requested, as with APK
libraries. Unsupported services and unknown formats remain explicit stops.

## Resource banks and local extraction

Numeric IPA files are read from the app's immediate `res_generated/` directory,
using canonical decimal filenames. The optional music bank above fills only
its verified missing IDs. Script-visible IDs are unchanged:
resources below 26000 come from the base game; resources at or above 26000 come
from the selected EXP. Script loading separately gives the episode's exact
script IDs priority. The iOS base/episode split is visible in
`SHSEngine::getData` at `0003dd60`.

Root-level EXP members are imported directly. The inspected app contains
The New Girl, SHS Season 1 and Novel Bonus Content. Its loose Football Star
scripts, 25001–25021, are collected into a deterministic local EXP with titles
from string bank 12, entries 193–197. The original script bytes and IDs are
preserved. These four stories were successfully imported; this is not a
complete-playthrough claim.

Host UI assets have a separate role mapping in `ios_assets.py`. Existing
Android role numbers are renderer keys, not aliases exposed to bytecode:

| UI purpose | Android role | IPA resource |
| --- | --- | --- |
| UI strings / layouts | 13 / 14 | 12 / 13 |
| Shared menu art / common skin | 16 / 126 | 15 / 125 |
| Dialogue skins | 204, 220, 236, 252 | 203, 219, 235, 251 |
| Portrait mask / picker skin | 268 / 272 | 267 / 271 |
| Football / grid sprite atlases | 290 / 446 | 289 / 445 |
| Remaining shared sprite atlases | 496, 499, 502 | 495, 498, 501 |
| CS glyph atlases and metrics | 508–533 | 506–531 |
| Hearts, skulls, smiles and flashes | 3010–3018 | 2615–2623 |

The inspected layout bank is identical to the Android layout bank. Native
relationship icon selection is at `0007d1c0`. Unmapped Android-only exports
are not guessed from neighboring numeric IDs.

IPA libraries use manifest version 2, profile `shs-ios-assets-v1`, and an `ipa`
record with `file`, `sha256` and informational `app` metadata. Bundled episode
records use `ipa_member`; copied EXPs retain `file`. Save content identity is
`profile`, `ipa_sha256`, and `episode_sha256`. The complete archive hash is
checked on open, so repacking changes save identity even when assets match.
Existing version-1 Android libraries and their save identities are preserved.

Adding APK music upgrades the manifest to version 3, with a `music_apk` record
containing `file`, `sha256` and `native_sha256`. Both the IPA and supplemental
APK archives are checked on open. This presentation-only supplement is excluded
from save identity so existing IPA checkpoints remain compatible. Older runtime
versions reject the version-3 library rather than silently ignoring its music.
The source profile, primary `ipa` record and episode records stay unchanged.

## Fonts

Native `SHSEngine::initFonts` (`0003c440`) requests Arial Rounded MT Bold,
Arial, Trebuchet MS Bold and Trebuchet MS Italic from the operating system.
The IPA supplies Pajama Hip at 505 and MonoNumerals at 504, plus its embedded
menu/CS glyph assets; it has no Android `.fnt`/PNG sets for the system faces.

For system faces, the desktop player first looks for an installed original
family and style and verifies the face returned by the font loader. If absent
or unreadable, it uses the platform's default UI font: San Francisco on current
macOS, Segoe UI on Windows, or fontconfig's configured sans-serif on Linux.
Fontconfig substitutions are accepted only on that fallback path. Bundled
Pajama Hip is preferred when present; without it, the same installed-face,
then system-default lookup applies. The owner explicitly requested this
fallback behavior. Asset import itself does not require installed fonts.

Pillow/FreeType renders these faces into an in-memory glyph atlas, cached per
open library. Font files and generated glyph images are not copied into the
application or its distribution. Font data is never fetched from a server.

This rendering path has not been proven pixel-identical to iOS CoreGraphics.
Fallback faces can change wrapping, pagination and name-width limits. Save
restoration validates saved dialogue and speaker layout, so moving an IPA
save to a system with different font metrics can fail that validation; use the
same fonts to resume such a checkpoint. Identical-font save/restore was tested.
The original Android bitmap-font path still reads its supplied atlas pixels.

## Platform-specific UI

Some Android UI images are exports of elements the iOS app constructs at
runtime. IPA playback uses the recovered iOS assets for these elements:

- Timed choices use common-skin frames 7–22. `GameModel::init` at `000242ac`
  supplies them to `SHSCircleTimerLayer` (`0002e758`, `0002ea94`, `0002eda8`).
  The sixteen wedges each consume 1/16 of the duration, retaining opacity 0.8
  for the first 40% of their interval before fading to zero. Remaining time,
  pause behavior and script timeout results keep the existing session contract.
- Name entry uses layout 46 and Pajama Hip at size 24, based on `000a0238`
  and `000a0880`. Prompt height controls panel height and vertical placement.
  UIKit supplies the original invalid-entry alert; the desktop version uses
  the existing blue message skin with the supplied alert strings. This modal
  is an explicit desktop adaptation, not a reproduced UIKit screenshot.
- Football down labels come from atlas 289, English frames 10, 15, 20 and 25
  (native table `00312772`). Feedback uses glyph atlas 508 and metrics 509.
  The selection ring uses frame 125, rotating once per second and scaled to
  half height, with opacity `0.7 + 0.3 * sin(seconds * 4)` (`0008efa8`).

Shared gameplay/host services continue to use the recovered Android ABI.
The system-font path, native iOS panel transitions, keyboard behavior and
complete iOS gameplay parity remain incomplete. Preserving identical shared
assets does not establish that all native platform behavior is identical.

## Audio and verification

The inspected `SHSSoundManager` constructor (`00074d74`–`000754ac`) sets the
same eleven music cue redirects and offsets as Android. Requests still retain
their original IDs. The IPA contains ten MP3 tracks: 8203, 8210, 8215 and
8226–8232. All ten are byte-identical to the corresponding supplied Android
tracks and play through the desktop resource loader and SDL mixer, including
the three cues that seek within these files.

The original iOS app downloads another ten tracks separately: **8201, 8205,
8207, 8209, 8212, 8217, 8219, 8221, 8223 and 8224**. This is established by the
startup calls at `0003972c`–`00039744`, `SHSEngine::resetResList` (`0003a3c8`),
`startResourceDownload` (`0003a538`) and `downloadResourceDone` (`0005094c`).
The queue is persisted in `shs_res_ist.bin`; downloaded bytes are written to
the app's data directory under decimal resource filenames. The native
`CSResourceMgr::getData` (`00017980`) tries the app bundle first, then that
directory. These ten tracks are absent from the supplied IPA and its extracted
app, but all are present in the supplied APK.

The New Girl's opening requests 8217, then 8201, then 8224, so its music stays
silent with this IPA alone even though the archive contains other playable
music. These requests were traced through actual story execution. The optional
APK import above supplies these tracks. Importing an iOS download cache and
contacting the original server are not implemented. Without the optional APK,
missing audio retains its existing diagnostic.

Optional local tests import all four stories and exercise The New Girl through
its first word game, including name entry and same-font save restoration.
Audio checks use the real SDL decoder with a dummy audio output; they do not
verify physical speaker output. They cover all bundled tracks, the optional
APK music and its alternate cues, plus adding music while a live story is
paused with a previously missing cue. Authored checks cover IPA precedence,
unchanged checkpoints, relocation, source validation and atomic failure paths.
Authored minigame calls also render the supplied football targets/feedback and
grid assets. Container, identity, required-asset and font-selection checks use
authored fixtures. No original files are added to tests.

Native addresses above refer to the supplied `Surviving_HS` binary, SHA-256
`9d779bd7a5d1fa3645281030e7ddadd36046edba04801fad23aa86682eb04fbe`.
This hash identifies research evidence only; it is not an import requirement.
