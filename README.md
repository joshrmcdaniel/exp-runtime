# SHS Runtime

An experimental compatible engine for **Surviving High School**, aiming to
reproduce the original interface and gameplay. It executes the original KiWi
scripts and reads graphics, fonts, audio and episode data from files supplied
by each player.

You need your own **SHS Android 1.0.9 APK** or **SHS IPA with compatible assets**,
plus any additional **EXP episodes** you want to play. The importer reads those
files locally. Game content is not included in this project or downloaded by it.
IPA import checks the SHS bundle identifier and required assets; its version
number is informational. See [IPA support](docs/IPA.md) for details.

## Download an app

Open this repository's **Releases** page and download the archive for your
system: `windows-x64`, `linux-x64`, `macos-arm64` (Apple Silicon), or
`macos-x64` (Intel). Extract it and open the app inside. Keep the complete app
or executable folder together. Python and the runtime dependencies are bundled.

For development builds, open **Actions → Desktop builds**, choose a successful
run, and download its platform artifact. Extract the artifact ZIP, then the
app archive inside it.

Builds include a SHA-256 checksum. macOS builds use ad-hoc signing and are not
notarized; Windows builds are unsigned. See [distribution](docs/DISTRIBUTION.md)
for CI triggers, packaging and the first-launch requirements.

## Build your own app

Install Git and uv, clone this project, then run from the project's directory:

```sh
uv sync --locked --extra build
uv run --locked --extra build python tools/build_desktop.py
```

No game files are needed during the build. Python 3.10 or newer is required;
uv prepares the local environment and installs the locked dependencies.

| Platform | App to open |
| --- | --- |
| macOS | `dist/desktop/SHS Runtime.app` |
| Windows | `dist/desktop/SHS Runtime/SHS Runtime.exe` |
| Linux | `dist/desktop/SHS Runtime/SHS Runtime` |

Build on the operating system where you will play. Keep the whole app or
executable directory together: it includes Python and its dependencies.
CI builds and checks all four targets. Local verification has covered macOS
on Apple Silicon; a successful CI run checks the other platforms' startup,
but full gameplay still needs testing on each system.

You can also run directly from source:

```sh
uv run --locked --extra desktop shs
```

## Add your game files

1. Launch the app and choose your APK or IPA on the setup screen.
2. Add EXP files or an episode folder through Options, or drag them onto the
   menu. The game's bundled episodes, including Football Star, are imported
   automatically.
3. Select an episode in Play/Resume. Imported episodes and progress persist
   when you close the app.

For an IPA, you can optionally supply your Android 1.0.9 APK through **Options →
Content Library → Add APK Music** to restore music the iOS app downloaded
separately. IPA artwork and installed original fonts keep priority, and your
IPA saves remain compatible. See [IPA import](docs/IPA.md#optional-apk-music)
for command-line options and supported assets.

> Store the episodes within a folder
>
> Example:
>
> ```
> Episodes/
>     Episode1.exp
>     Episode2.exp
>     ...
> ```

If your episode folder includes the original `shs_options.sav`, its category
catalog supplies the original season/story groups. It can also be added
separately. Without that optional file, unknown groups use numeric pack names.

Existing libraries from `exp-decoder-python` still work: choose **Open Library**
and select the existing library directory. It can stay outside this project.
Existing Android content identities and saves are preserved. IPA libraries
use a separate source profile and installed fonts, falling back to the system
default when an original face is absent. See [runtime setup](docs/RUNTIME.md)
for paths, controls, formats and command-line import.

## Current state

The runtime implements the main menu, persistent episode library, grouped
episode browser, dialogue animation, portrait masks, choices, character
selection, relationship indicators, episode/week intros, loading screens, word/grid/football mini
games and save/load. F5 saves, F9 loads, and returning to the menu creates an
automatic checkpoint. Tap once to reveal dialogue, then again to advance it.

The New Girl opening and Football Star opening through its first football
game have been exercised. Complete episode playback and full 1:1 visual/timing
equivalence are still being verified. Unsupported services stop explicitly
with their scene, service and program counter. Current limits are recorded in
[RUNTIME.md](docs/RUNTIME.md) and [ENGINE_ABI.md](docs/ENGINE_ABI.md).

## Specifications and development

To contribute code, tests, documentation or compatibility reports, start with
[MAINTAINERS.md](MAINTAINERS.md).

- [EXP format](docs/SCHEMA.md): container, index, compression, metadata and payloads.
- [KiWi VM](docs/VM_SPEC.md): bytecode, all core opcodes, memory, calls and yields.
- [Engine services](docs/ENGINE_ABI.md): native service contracts and coverage.
- [UI assets](docs/UI_ASSETS.md) and [UI fidelity](docs/UI_FIDELITY.md).
- [IPA import and system fonts](docs/IPA.md).
- [Main menu](docs/MAIN_MENU.md) and [episode catalog](docs/EPISODE_CATALOG.md).
- [Episode introductions and week cards](docs/TITLE_SCREENS.md).
- [Mini games](docs/MINIGAMES.md) and [story services](docs/STORY_SERVICES.md).
- [Development and tests](docs/DEVELOPMENT.md), [distribution](docs/DISTRIBUTION.md)
  and [project provenance](docs/PROVENANCE.md).
- [Release notes](RELEASE.md) and [changelog](CHANGELOG.md).

Run the full test suite from the repository root with the command below.
See [Running unit tests](MAINTAINERS.md#running-unit-tests) for dependency
setup, running individual tests and interpreting optional skips.
For checks against your APK and episodes, follow
[Testing with your own game files](MAINTAINERS.md#testing-with-your-own-game-files)
to place the inputs and create the local test library.

```sh
uv run --locked --extra desktop python -m unittest discover -s tests
uv run --locked shs-tool --help
```
