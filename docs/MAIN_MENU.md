# Main menu and desktop application contract

Reference: SHS Android 1.0.9, `libshs09.so`, SHA-256
`b17aa4c71bc46666d414cafae6fac92bbcd755f3dcccd73975cf05f4a119665b`.
Addresses below refer to that loaded binary. The Android interface is the
working reference for the shared interface described by the user.

## 1. Native application states and commands

The main menu is outside the KiWi VM. `FUN_00090818` switches application
states; `FUN_000de258` handles its buttons. These commands are **not** script
yield IDs and must never be fed into the engine-service dispatcher.

| Native state | Meaning | Native constructor/setup |
| --- | --- | --- |
| 101 / `0x65` | Main menu, input enabled | `000861c0`, `000deac4` |
| 110 / `0x6e` | Play/Resume selection | `0007ad74` |
| 111 / `0x6f` | Options | `00076c7c` |
| 112 / `0x70` | Help/About | `0006ee04` |
| 105 / `0x69` | Episodes on demand/network listing | `00090818` |
| 107 / `0x6b` | Weekly episode/network listing | `00090818` |

| Button tag | Native action | String-bank ID | Desktop action |
| --- | --- | --- | --- |
| 10002 | Play/Resume | 125; 126 if a save exists | All installed episodes, with saved-progress indicators |
| 10004 | NowAiring | 127 | Locally imported episode list |
| 10003 | OnDemand | 91 | All local episodes |
| 10005 | MoreGames | 252 or 253, depending on ad state | Explain local-content workflow; no store request |
| 1006 | Options | Gear artwork | Music/Sound toggles and library controls |
| 10007 | Help/About | Info artwork | Player controls and reconstruction status |
| 10008 | DisableAds | 300 | Omitted; no advertising or purchase system |

`0008cfe4` checks native save availability; `0008ce68` distinguishes the New
Girl save from the current expansion save. Native save formats are not read by
the compatible runtime. The native analytics names and visible English labels
differ: string 127 is "Weekly Free Episode", and 91 is "More Episodes".
Labels are loaded from the player's APK, not embedded as copied game data.

Native button handling rejects input during a transition and unless the
application is in the main-menu state. Selection feedback uses sound 8010.
Native network listings refer to server-provided episode/ad configuration.
The desktop lists the user's own EXP files instead; it neither contacts those
servers nor pretends that a local episode is the latest weekly release.

## 2. Artwork and layout

All menu resources are read directly from the **APK bank**, before any episode
is opened. This avoids requiring an arbitrary episode to render application UI.

| Resource | Use |
| --- | --- |
| 6 | 320 × 480 wooden background |
| 7 | 303 × 104 title logo |
| 8 | 336 × 69 dark ribbon |
| 9 | 477 × 398 character photograph |
| 13 | Byte-string bank |
| 14 | Layout bank |
| 16 (`16.mp3`) | Episode rows, navigation icons, blue/orange buttons |
| 126 | Common UI art |
| 204 | Blue window border |
| 272 | Gold menu-button pack, background wedge, gear and info icons |
| 532 / 533 | Embedded menu glyph fonts; 532 used for main labels |

`000dfde8` loads 272 and binds it to layout image slot 5. Layout 74 describes
the 275 × 135 menu group. Layout 79 supplies its 109px-high backdrop;
75/77 are normal/pressed three-piece gold buttons. `000e0988` independently
constructs the four live buttons from 75/77. The default width is **184px**;
it is not the 205px placeholder width found by flattening layout 74.

`000df488` sets the staggered horizontal destinations. `00147df8` centers
four 28px-high buttons vertically with 5px gaps. With the ad-free fourth
button width 155, the reconstructed top-left rectangles, rounded to pixels,
are `(14,344,184,28)`, `(40,378,184,28)`, `(26,410,184,28)` and
`(13,444,155,28)`. `menu.main_button_rects()` derives them from the APK's
layout dimensions and these native placement operations. Half-pixel origins
are rounded at rasterization. The gear and info controls occupy the lower
right corner. The desktop uses the ad-free arrangement.

`000df868` centers the background/photo at logical `(160,240)`;
`000dfa48` centers the title/ribbon at GL `(160,384)`, or top-origin y=96.
The title ribbon rotates -5 degrees in the native clockwise convention.
Logical rendering is 320 × 480, scaled uniformly into a resizable desktop
window with letterboxing; pointer coordinates use the inverse transform.

Native list assets recovered through `0006ca44`/`0006cf00` and layouts
62/63 supply 296 × 42 alternating episode rows, with status icons 96 (pause),
97 (replay), and 101 (play) from pack 16. Layouts 70/71 provide the blue
normal/pressed footer buttons. The desktop uses those resources with local
metadata, scrolling, and a searchable list. The native category strings retained
in the user's `shs_options.sav` organize the list into collapsible sections;
saved games also appear as shortcuts at the top of Play/Resume. Headers use
original frame 76 and font registry 2. Search includes category names and
temporarily expands results. By Number / By Title sorts within sections and
remembers the choice. Default ordering uses `(pack_id, episode_id, title)`,
with bundled versions first for matching IDs and titles. Unknown categories
use numeric pack headers. Matching titles distinguish bundled and imported
versions rather than merging different EXP hashes. The complete catalog schema,
native evidence, import behavior and desktop adaptations are documented in
[EPISODE_CATALOG.md](EPISODE_CATALOG.md).

## 3. Additional resource schemas

### String bank (resource 13)

All integer fields are big endian. The supported asset has this structure:

```text
version        : s32 = 1
flags          : u8  = 0
bank           : s16 = 0
string_count   : s16 = 303
offsets        : s16[string_count]  # Absolute byte offsets from file start
strings        : NUL-terminated byte strings
```

`00058de4` reads the three header fields, count, and offsets. It subtracts 9
when copying offsets into its own headerless in-memory buffer. `00058d4c`
indexes those offsets by `2 * string_id`. These strings use byte characters,
unlike EXP metadata's UTF-8 titles. Dynamic `~number~` substitutions are handled
by `00058bc4` through the application's string callback; the main-menu labels
used here are static. The parser validates all offsets and terminators. It does
not implement substitutions for unrelated strings in this bank.

### Embedded menu glyph font (532 / 533)

```text
space_width    : s8  = 5
style          : u8  = 0
tracking       : s8  = -2
glyph_count    : s16 = 88
height         : s8  = 24
character      : u8[glyph_count]
pixel_marker   : s16 = -1
image_count    : s16 = glyph_count
for each glyph:
    width      : u8
    height     : u8
    pixels     : (A,R,G,B)[width * height]
```

The character lookup and every pixel come from the asset. Lowercase labels
fall back to their uppercase glyphs; spacing uses the stored tracking. This
is a different representation from the external-atlas fonts 529/531/541 and
the named `.fnt` descriptors. `000e0988` explicitly selects 532 for the first
three labels and 533 for the fourth; the renderer follows that selection.

## 4. Lifecycle and persistence

```text
No library -> Setup -> Choose/drop APK or IPA -> Validate/copy -> Main menu
Main menu -> Play or episode list -> Episode -> Play/Resume -> Session
Session -> Pause -> Main menu -> Automatic checkpoint -> Main menu
Session -> Service 7/63 -> Terminal checkpoint -> Main menu (no Resume)
Main menu -> Options -> Add EXP files/folder -> Validate/copy -> Episode list
```

The file picker is implemented inside the application, so a packaged app does
not need a terminal, Python installation, Tk, or an external file-dialog
utility. Files and whole episode folders can also be dropped onto the menu.
A multi-file SDL drop is collected into one import transaction. Parsing and
copying run on a worker; the render/event loop continues at 60 Hz.

Initial imports stage a new library and publish by directory rename.
`ContentLibrary.add_episodes()` stages and validates the entire batch before
atomically replacing `library.json`. SHA-256 deduplication preserves existing
records, the original inputs, and saved progress. A failed validation changes
neither the manifest nor the content files. A crash during the final file moves
can leave unreferenced content files, but cannot publish a half-written manifest.
Use one writer per library; a manifest change detected since opening aborts the
import. This is not a multi-process database locking protocol.

The application holds one live session. Menus and unfocused windows do not
tick its dialogue, choice or mini-game clocks. Returning through Main Menu
checkpoints it; resuming that episode reuses the live session exactly. Starting
a different episode constructs fresh renderers and image caches, preventing
episode-specific IDs from reusing the old episode's images. Unsupported VM
services remain suspended and visible to the player.

Services 7/63 end the episode, cancel its queued scripts and retire ordinary
Resume progress. The application stores a terminal automatic checkpoint,
stops audio and releases that live session. A validated terminal checkpoint
masks older saves for Resume; the manual F5 slot remains available to explicit
Load. Starting the episode again creates a fresh session. Other episodes'
progress is unchanged. A failed checkpoint retains the terminal live session
and reports the write error. See the [exit contract](STORY_SERVICES.md#episode-exit-services-7-and-63).

| File, relative to the library | Schema / behavior |
| --- | --- |
| `player.json` | `{version:1, selected:SHA256, music:bool, sound:bool, order:"episode"\|"title"}`; old files default to episode order |
| `saves/<episode-sha>.shs-save.json` | Existing manual F5/F9 slot, [runtime save schema](RUNTIME.md#runtime-save-schema-version-13) |
| `saves/<episode-sha>.shs-auto.json` | Automatic checkpoint on menu return and application exit, same schema |

Preferences and saves use temporary files plus atomic replacement. Resume after
restart chooses the newer automatic/manual file, then validates its full
profile/APK/episode identity through `Session.load`. A valid terminal checkpoint
suppresses Resume rather than falling back to older progress. A bad save is reported;
it is not silently replaced by a fresh game. New Game has an in-app restart
confirmation when progress exists. Subsequent checkpoints replace the automatic
slot; the manual slot is preserved. Existing libraries without preferences use
their most recent save, or the New Girl metadata ID `(5,9)` when no save exists.

Music/Sound preferences gate playback separately from VM-visible audio state.
Leaving a live episode pauses its music stream; resuming that same session
continues from its current position. Starting another episode, restarting, or
loading a saved session instead loads its requested cue. Playback position is
not saved to disk, and no native menu music loop has been verified.

## 5. Executable and content boundary

`shs`, `python -m shs_runtime.application`, and `shs-tool play` launch the menu.
`--library` selects a relocatable content directory. A source checkout uses an
existing `.shs-library`; otherwise the default is per-user application data:

- macOS: `~/Library/Application Support/SHS Runtime/library`
- Windows: `%LOCALAPPDATA%/SHS Runtime/library`
- Linux: `$XDG_DATA_HOME/SHS Runtime/library`, defaulting to `~/.local/share`

A frozen executable uses application data independently of its working directory
or extraction location. **Open Library remembers the chosen folder** in
`SHS Runtime/launcher.json` beside the default library. Its schema is
`{version:1, library:absolute_path}`; publication is atomic. Subsequent launches
use that library, including source launches from a different working directory.
An explicit `--library` is a launch override and does not change the remembered
default. Imported episodes appear in Play/Resume even before they have saves.

Build on the target operating system:

```sh
uv sync --locked --extra build
uv run --locked --extra build python tools/build_desktop.py
```

The build creates `dist/desktop/SHS Runtime.app` on macOS and a
`dist/desktop/SHS Runtime` executable directory on other systems. Distribute the
whole app/directory. The build entry point is a temporary authored launcher;
LICENSE is the only repository file explicitly collected as data. Runtime
modules, Python, pygame/SDL, dependencies and their support files ship; **no
APK, EXP, extracted game assets, original native executable, screenshots,
decompilation, library manifest or save files ship**. Users import their data
on first launch. The same build works from a source checkout without any game
files; see [DISTRIBUTION.md](DISTRIBUTION.md). Build and inspect each platform
independently; creating the macOS app does not validate a Windows or Linux
executable. See the official
[PyInstaller build options](https://pyinstaller.org/en/stable/usage.html).

## 6. Verification boundary

The main artwork, glyphs, original button commands and static geometry are
grounded in native code/assets. Full screenshot/recording equivalence is not
yet established. Known adaptations and gaps:

- Local episode lists, search, setup, file picker, help content and library
  controls replace server/purchase/platform flows.
- Options implements audio and content management, not all original native
  settings. Original episode preview/download details are not reconstructed.
- Entrance models the one-second photo scale, title at 1.1s, menu backdrop at
  1.6s, and staggered 250/500/750/1000ms buttons starting at 2s. Native
  `000dede4`/`000df168` subsequently fade the info button and grow the gear;
  these appear immediately at 3s here. Returning main menu uses a 500ms slide;
  submenus use a 200ms crossfade rather than the full native panel movement.
- Save formats and automatic checkpoints are compatible-runtime features,
  not emulation of the original binary `.sav` files.

Tests cover authored string/font records, failed-batch atomicity, deduplication,
manual/automatic save separation, corrupt resume behavior, first launch without
content, multi-file drops, menu input gates, resized hit testing, long-list
search/scrolling, pause timing and exact live resume. Optional visual tests use
the player's local library; they do not package it as a fixture.

## Built-in story extraction

Football Star is not an APK `.exp` member. Its scripts are loose numeric assets:
25001–25021 and 25023. The importer copies all 22, byte for byte and under the
same IDs, into a deterministic local CSPUD archive with literal records.
Metadata resource 1 has pack/episode IDs 0/0; `FUN_0008b048` identifies the
Football save by native key zero, and `FUN_0009794c` composes that key from the
pack and episode shorts. The five title strings are read from APK resource 13,
entries 193–197. The catalog filename is `Football_Star.exp`.

The resulting record has an ordinary hash-derived `file` location plus
`builtin: "football-star"` and text search aliases, including Football Season.
These optional manifest fields do not change library schema version 1. Art,
fonts and audio keep their original APK namespace. No proprietary EXP or
metadata blob is embedded in the executable; every extraction requires a
validated user APK, which the library retains.

Fresh imports include this story automatically. Application startup and CLI
listing call `ensure_builtin_episodes()` to upgrade earlier libraries from the
retained APK. Publication uses the same staged, validated, atomic manifest
update as added episodes, checking for concurrent edits. Existing episode
identities, player preferences, and manual/automatic saves are preserved.
Repeated upgrades do not duplicate the entry. Numeric order puts it at 0/0;
it is classified as bundled even though its generated EXP is a local file.
The local library now contains 272 episodes and 996 script records. A startup
audit reached 179 title screens and 93 dialogue screens with no failures;
these counts establish initialization, not full-story compatibility.

Football Star's opening, appearance selection, name entry, dialogue choices
and first classes have been tested using original bytecode. Service 91 at
scene 25006, PC 1245 now completes into the first football mini game. The tested
route plays both halves and returns to dialogue. Relationship indicators now
render with native icon/count selection, cache writes, sound and animation;
see [UI_FIDELITY.md](UI_FIDELITY.md#npc-relationship-indicators).
