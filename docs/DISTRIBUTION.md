# Source distribution and local builds

EXP Runtime provides the compatible engine, KiWi interpreter, local asset
importer, authored specifications, tests and build tools. Each player supplies
an SHS Android 1.0.9 APK, compatible SHS IPA, or CoD IPA, plus additional EXP files. The original
ARM executable is inspected only to identify the supported APK profile; it is
not executed by the runtime. IPA import identifies the game by bundle identifier
and validates its required assets, independently of the version number.
System-font fallback and current limits are in [IPA.md](IPA.md) and [COD.md](COD.md).

## Downloads built by GitHub Actions

[Desktop builds](../.github/workflows/desktop-builds.yml) runs on branch pushes,
pull requests, version tags beginning with `v`, and manual **Run workflow**
requests. It installs locked dependencies with uv and Python 3.14, runs the
tests without game content, builds the app, audits its bundle and tests the
extracted download. Third-party actions are pinned to verified commit hashes.

| Download target | GitHub runner | Archive |
| --- | --- | --- |
| `windows-x64` | `windows-2022` | ZIP containing the full executable directory |
| `linux-x64` | `ubuntu-22.04` | tar.gz preserving executable modes and links |
| `macos-arm64` | `macos-14` | ZIP containing the Apple Silicon app |
| `macos-x64` | `macos-15-intel` | ZIP containing the Intel app |

After a successful run, development downloads are under **Actions → Desktop
builds → the run → Artifacts**, with one artifact per platform. Each contains
an app archive and its `.sha256` checksum; extract the outer artifact ZIP and
then the app archive. These artifacts expire after 30 days. GitHub requires
sign-in and repository read access for [Actions artifact downloads](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts).

The owner can publish a version by pushing a tag such as `v0.1.0`. Once all
four builds pass, the release job verifies the downloaded checksums and
publishes their archives/checksums on **Releases**. A tag containing a hyphen,
such as `v0.1.0-rc.1`, creates a prerelease. Ordinary pushes and pull requests
never create releases. Their jobs have read-only repository permissions; only
the version-tag release job has `contents: write`, using GitHub's built-in
token. No personal token or signing secrets are required.

The release body comes from [RELEASE.md](../RELEASE.md) at the repository root.
Update it before tagging a version. [CHANGELOG.md](../CHANGELOG.md) records
release history, with upcoming changes under **Unreleased**.

Rerunning a version-tag workflow updates matching assets on an existing
release using `gh release upload --clobber`, then publishes any draft left by
an interrupted upload. If GitHub release immutability is enabled, publish a
new version tag instead. The workflow does not commit,
push code or create a tag; the release command requires the tag to exist.

Until the owner pushes this workflow, there are no CI-produced downloads.
Cross-platform success must be confirmed by its first GitHub run. Local
macOS validation alone does not establish Windows/Linux compatibility.

## Player workflow

After cloning the project, run from its root directory:

```sh
uv sync --locked --extra build
uv run --locked --extra build python tools/build_desktop.py
```

Open `dist/desktop/EXP Runtime.app` on macOS. Windows and Linux executables
are inside `dist/desktop/EXP Runtime/`; keep that complete directory together.
Build on the target operating system. CI adds startup checks for all four
download targets; complete gameplay still needs validation on each platform.

The build bundles Python and the runtime dependencies. No APK, IPA, EXPs, Ghidra,
Ren'Py SDK, extracted resources or old checkout are required to build it.
On first launch, choose SHS or CoD, supply its APK/IPA, and add its episode files.
Extraction happens locally; the application has no game download service.

To run from source instead:

```sh
uv run --locked --extra desktop exp-runtime
```

Libraries and saves stay in the user's application-data directory or another
folder they choose. Existing libraries from the research project can be opened
through **Open Library**. Building or updating the engine does not require
copying game content into this source directory. See [MAIN_MENU.md](MAIN_MENU.md)
for library locations and [RUNTIME.md](RUNTIME.md) for current compatibility.

## Public project contents

This standalone directory was assembled from authored source and documents.
It includes no Git history from the research project. Git initialization,
remotes, commits and publication are left to the project owner.

Keep APKs, IPAs, extracted images/audio/fonts/scripts, original screenshots,
native decompilations, generated games, runtime libraries and player saves
outside the public tree. Optional original-content tests read local inputs
and skip when those inputs are absent; ordinary tests use synthetic fixtures.

- `.gitignore` excludes known local game/research paths and generated output
  from normal Git staging. It does not exclude already tracked files.
- `MANIFEST.in` explicitly selects authored source, tests, tools, docs and the
  kiwi SVG logo for source packages. Setuptools limits Python packages to
  `src/exp_runtime` and explicitly includes only `assets/kiwi.svg` as package data.
- `tools/build_desktop.py` bundles the runtime and its dependencies. `LICENSE`
  and the authored kiwi SVG are the only repository files explicitly collected
  as executable data. The build renders the SVG into a macOS ICNS or Windows
  ICO using the existing pygame/Pillow dependencies; no game files are needed.
  The SVG also supplies the launcher logo and window icon on all platforms.
- `tools/package_desktop.py` archives only the expected app bundle/directory,
  rejecting known game inputs, research files and external links. The workflow
  uploads only `dist/downloads`, never the workspace or content library.

The macOS archiver uses `ditto` to preserve framework links, executable bits
and the app's ad-hoc signature. The archive is extracted again and checked
with `codesign --verify --deep --strict` before the setup-screen smoke test.
Linux downloads use tar.gz because ordinary Actions ZIP uploads do not retain
[file permissions](https://github.com/actions/upload-artifact#permission-loss).
Windows ZIP downloads include the complete PyInstaller output directory.

Apple Developer ID signing/notarization and Windows Authenticode signing are
not configured. macOS may block the initial launch pending approval in Privacy
& Security; Windows may show an unknown-publisher prompt. These are local
builds of an experimental engine, with no original game content included.

Research commands can produce traces containing game text and local paths.
Their JSON outputs belong in ignored local directories, not in the published
source. The format and VM specifications retain evidence addresses and
historical verification summaries. See [PROVENANCE.md](PROVENANCE.md) for how
to interpret references to private evidence snapshots.
