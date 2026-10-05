# v0.3.0

**Renamed from shs-runtime to exp-runtime**

## Fixed

- Implement SHS service 15's named dialogue, including its optional negative
  prefix and ignored extra arguments, using the shared dialogue renderer.
  Native defaults 14/21 now complete with zero. Existing saves stopped at
  these services resume without restarting the episode. Verified with both
  APK and IPA assets and original imported callers.
- CoD service 100 now follows the supplied native runtime's return-zero path,
  allowing promotional-link choices in What Happened to Colt, Part 2 and
  Dead Man Walking, Part 1 to continue. Existing saves stopped at these calls
  resume the actual remaining script; no browser or other app is opened.
- Read CoD's native `cod_options.sav` catalog so imported episodes use their
  original volume and category names. Folder imports, individual EXP imports
  and the episode picker now discover the selected game's catalog. The shared
  matching and update behavior also applies to SHS's `shs_options.sav` in
  existing and newly imported APK/IPA libraries.
- Preserve alternate filenames when identical EXPs are imported again in
  either game, allowing catalogs to match renamed copies. Existing content
  deduplication keeps one entry per EXP hash and preserves saved progress;
  different editions with the same title remain separate.
- Correct dialogue names and text placement with IPA fonts in both games,
  using their verified native wrapping, font metrics and normal/tall headers.
  Long names retain their original size and may straddle the box border.
  Body text stays in its own region; expanding the header no longer crowds
  the first line or adds body capacity. The shared renderer fits fallback
  glyphs/outlines to the selected header without character or scene overrides.
  Existing IPA saves retain progress and reflow the current page once.
- Correct CoD's normal dialogue to black text with dark-red speaker names,
  using its own native palette instead of SHS's blue. Theme colors remain
  separate from the shared layout.
- Share v0.1.3's SHS dialogue skin between SHS and CoD, across APK and IPA
  libraries, with each game's own artwork and native font rules. Android
  bitmap-font geometry/history and common narration/animation remain supported.
  Older IPA checkpoints reflow at their saved reading position without
  replaying the story; libraries do not need to be reimported.

## Added

- A kiwi fruit app logo, drawn as an SVG and shown in the game chooser and
  window icon. Desktop builds generate macOS and Windows app icons from it.
- Implement CoD's build/platform queries (service 70), including the supplied
  IPA's version string and the native store-unavailable result on desktop.
  Services 94/96 now follow CoD's native return-zero paths. Existing saves
  stopped at these calls resume without replaying previous story actions.
- Choose Surviving High School or Cause of Death in the launcher. Each game
  requires its own supplied assets and keeps a separate library and progress.
  **Options → Switch Game** checkpoints the current story before switching.
- Import a compatible CoD IPA, including its bundled Volume One EXP. CoD uses
  its own UI strings, fonts, relationship assets and nine music sources.
  Service 15 supports named dialogue; service 99 follows the offline no-ad
  continuation. Unverified services still stop explicitly; see [CoD support](docs/COD.md).

### Changed

- Rename the project/package to `exp-runtime` / `exp_runtime`, with
  `exp-runtime` and `exp-tool` commands. `shs` and `shs-tool` remain aliases.
- Organize game-specific code under `exp_runtime/shs/` and `exp_runtime/cod/`.
  The EXP reader, KiWi VM, common panels, saves and launcher remain shared.
- New libraries identify the game explicitly. Existing SHS APK/IPA libraries,
  launcher locations and saves remain supported without moving player files.
  Matching numeric resource IDs never resolve against the other game's assets.