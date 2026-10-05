# Main menu and desktop application contract

Reference: SHS Android 1.0.9, `libshs09.so`, SHA-256
`b17aa4c71bc46666d414cafae6fac92bbcd755f3dcccd73975cf05f4a119665b`.
Addresses below refer to that loaded binary. The Android interface is the
working reference for the shared interface described by the user.

EXP Runtime first presents an asset-free game chooser. SHS and CoD each open
their own validated library and game menu; the SHS evidence below does not
establish complete CoD presentation parity. [COD.md](COD.md) records its bindings.

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
| 1006 | Options | Gear artwork | Music/Sound, episode title language and library controls |
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
in the user's `shs_options.sav` or CoD's `cod_options.sav` organize the list
into collapsible sections; saved games also appear as shortcuts at the top
of Play/Resume. Headers use
original frame 76 and font registry 2. Search includes category names and
temporarily expands results. By Number / By Title sorts within sections and
remembers the choice. Default ordering uses `(pack_id, episode_id, title)`,
with bundled versions first for matching IDs and titles. Unknown categories
use numeric pack headers. Matching titles distinguish bundled and imported
versions rather than merging different EXP hashes. The complete catalog schema,
native evidence, import behavior and desktop adaptations are documented in
[EPISODE_CATALOG.md](EPISODE_CATALOG.md).

### Episode title languages

Options exposes the five EXP metadata slots in their observed order: English,
French, Italian, German and Spanish (`en`, `fr`, `it`, `de`, `es`). The language
names are read from original menu strings 118–122. The preference changes list
rows, episode detail titles, desktop captions and By Title ordering. Search
and exact episode selectors accept all five supplied titles; ambiguous matches
still require an ID. Empty/whitespace translations fall back to the English
title, then the filename if English is empty too. Repeated English titles are
displayed as supplied. Catalog grouping and content identity retain their
original keys.

This is a desktop metadata preference, not a recovered dialogue-language
switch. Inspection of the supplied Android 1.0.9 APK and iOS 1.4.2 IPA found
one 303-entry UI string bank in each (13 and 12, respectively), and no alternate
translated scene scripts. iOS `SHSEngine::getLanguageIndex` (`0003dd48`)
returns 0; `getLanguageCode` (`0003dd50`) returns English. `loadLanguageCSL`
(`0003a074`) loads resource 12, and `CSLocalizer::loadCSL` (`00013350`) reads
a single offset/string table. The language labels and some multilingual art
do not establish that a complete translation is present. Service 70 and script
resource IDs retain their verified contracts.

The extracted APK's 2,840-byte `resources.arsc` has no locale-specific resource
configurations; its string values are English launcher/connection labels.
The IPA root `Localizable.strings` is a binary plist with seven
`default_ticket_string_*` entries: EA Mobile promotional text in English,
French, Italian, German, Spanish, Korean and Chinese. It supplies no story or
game-menu translations. These observations apply to the inspected files, not
every historical regional build.

Android's supplied bitmap fonts have no accented glyphs. Menu labels which
need them use the installed Arial Rounded MT Bold face, then pygame's default
font when absent. Other menu labels retain their original bitmap metrics;
IPA's existing original-font lookup remains first. This fallback is confined
to desktop menu text. Story font/layout validation is independent of the
title-language setting. Choosing a title language preserves live sessions and existing
manual/automatic checkpoints.

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
IPA library -> Options -> Content Library -> Add APK Music -> Validate/copy -> Library
```

The file picker is implemented inside the application, so a packaged app does
not need a terminal, Python installation, Tk, or an external file-dialog
utility. Files and whole episode folders can also be dropped onto the menu.
A multi-file SDL drop is collected into one import transaction. Parsing and
copying run on a worker; the render/event loop continues at 60 Hz.

An initial drop containing one IPA and one APK uses the IPA as the base game
and the APK only for its verified missing music. An existing IPA library also
accepts a single dropped APK or the **Add APK Music** file picker, which filters
for `.apk` files. The library panel shows the missing track count and offers
the action only while tracks are absent. Music import preserves the live story,
checkpoints and loaded audio; Resume retries a cue whose earlier load failed.
See [IPA.md](IPA.md#optional-apk-music) for asset precedence and manifest version 3.

Initial imports stage a new library and publish by directory rename.
`ContentLibrary.add_episodes()` stages and validates the entire batch before
atomically replacing `library.json`. SHA-256 deduplication preserves existing
content identities, the original inputs, and saved progress in both games.
An identical EXP imported under another filename adds a lookup alias, allowing
catalogs to name that existing entry; it does not add another episode. Only
the selected game's catalog is discovered and shown in the file picker.
A failed validation changes neither the manifest nor the content files.
A crash during the final file moves
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
| `player.json` | `{version:1, selected:SHA256, music:bool, sound:bool, order:"episode"\|"title", title_language:"en"\|"fr"\|"it"\|"de"\|"es"}`; old files default to episode order and English titles |
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

`exp-runtime`, `python -m exp_runtime.application`, and `exp-tool play` launch
the game chooser. `shs` / `shs-tool` remain command aliases. `--game shs|cod`
opens one game directly; `--library` opens a specified relocatable library.
New libraries default to per-user application data, replacing `<game>` with
`shs` or `cod`:

- macOS: `~/Library/Application Support/EXP Runtime/libraries/<game>`
- Windows: `%LOCALAPPDATA%/EXP Runtime/libraries/<game>`
- Linux: `$XDG_DATA_HOME/EXP Runtime/libraries/<game>`, defaulting to `~/.local/share`

A frozen executable uses application data independently of its working directory
or extraction location. **Open Library remembers the chosen folder** in
`EXP Runtime/launcher.json`. Its schema is
`{version:2, libraries:{shs:absolute_path, cod:absolute_path}}`; either game
may be absent. Publication is atomic and preserves the other game's location.
Selecting a game uses its remembered library across working directories.
Existing v1 launcher preferences in `SHS Runtime` and its default `library`
folder remain discoverable in place. Source checkouts additionally discover
`.shs-library`. No original player files are moved or rewritten by discovery.
An explicit `--library` is a launch override and does not change the remembered
default. Imported episodes appear in Play/Resume even before they have saves.

**Options → Switch Game** checkpoints a live session before closing its library,
stops audio and discards per-game rendering caches. If the checkpoint fails,
the session stays open. The other game loads its own preferences and saves.
Setup rejects packages/libraries belonging to the other selected game.
EXPs themselves have no reliable game marker and must be added to the correct
selected library. SHS APK supplementation is unavailable for CoD libraries.

Build on the target operating system:

```sh
uv sync --locked --extra build
uv run --locked --extra build python tools/build_desktop.py
```

The build creates `dist/desktop/EXP Runtime.app` on macOS and a
`dist/desktop/EXP Runtime` executable directory on other systems. Distribute the
whole app/directory. The build entry point is a temporary authored launcher;
LICENSE and the authored kiwi SVG logo are the only repository files explicitly
collected as data. The game chooser and window use this logo; macOS and Windows
app icons are generated from the same SVG during the build. Runtime modules,
Python, pygame/SDL, dependencies and their support files ship; **no
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
- Options implements audio, episode title language and content management, not all original native
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
