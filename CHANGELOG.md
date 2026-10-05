# Changelog

User-visible changes are recorded here. Changes awaiting a versioned release
are listed under Unreleased.

## Unreleased

### Added

- Choose English, French, Italian, German or Spanish episode titles in Options.
  The preference applies to episode lists, title sorting and desktop captions;
  search and episode selectors accept all supplied titles. Missing translations
  fall back to English. Story text keeps the supplied episode's language, and
  existing saves remain compatible. CLI lists accept `--title-language`.
- Import an SHS IPA through setup, drag-and-drop, or `shs-tool import --ipa`
  as an alternative to the Android APK, including its bundled episodes and
  Football Star. Import identifies SHS by its bundle identifier and validates
  required assets; version and build numbers are informational.
- IPA playback uses its original UI assets, including its timer wedges,
  name-entry panel and football graphics. System fonts use the installed
  original face when available, then the system default. Font rendering and
  missing-content limits are documented in [IPA support](docs/IPA.md). The
  inspected IPA omits ten music tracks the original app downloaded separately;
  scenes requesting these tracks remain silent with the IPA alone.
- Optionally supply an Android 1.0.9 APK to restore missing IPA music during
  import or later through **Add APK Music** / `shs-tool add-music`. IPA assets
  and original installed fonts keep priority. Existing IPA saves and live
  story progress are preserved; no server download is required.

## v0.1.3

### Added

- Episode surveys now show “Thanks for taking the survey!” locally and continue
  any remaining story, without sending responses to a server. Saves stopped at
  survey submission recover without repeating the questions.

### Fixed

- Implemented Android's randomized choice order. Choices preserve
  their script return values and saved random state. Existing saves stopped
  there now resume without replaying earlier progress or reimporting content.

## v0.1.2

### Fixed

- Corrected dialogue portraits sitting too high inside their circular frames.
  The native 12-row crop and center placement now apply consistently in
  dialogue, choices and the appearance picker, including odd-height artwork.
- Fixed the imported New Girl episode's portrait-mask error. Larger portrait
  variants now render at half size before masking, preserving aspect ratio,
  transparency and orientation. Existing libraries need no content reimport.
- Timed choices now show the original circular countdown and timer panel.
  The timer stays visible when long lists scroll, freezes while paused or
  unfocused, and restores from saved time. Corrected expiry to occur just after
  zero, preserving the script's timeout selection and custom return values.
- Fixed the APK-bundled New Girl episode stopping at `yield 91 at pc 60:
  expected 1 arguments, got 0`. Loading now accepts both bundled and imported
  episode calls, preserving their native timer and VM frames through save/load.
  Existing libraries need no content reimport.
- Restored the name-entry screen's original panels, bitmap fonts, layout,
  cursor and invalid-input alert. Typing now follows the native capitalization,
  alphanumeric, 16-character and width rules, with Return to confirm. Drafts
  survive save/load, and rejected input leaves the pending script unchanged.

## 0.1.1

### Fixed

- Implemented services 7/63 for episode exit, fixing Football Star scene
  25001, PC 130. Endings now cancel queued scripts and return to the main menu.
  Save version 12 recovers older stops there and retires ordinary Resume
  progress while preserving manual saves and other episodes' checkpoints.
- Implemented service 70's verified Android query constants, fixing Football
  Star scene 25001, PC 222 (selector 10). Existing saves stopped at fixed
  queries now continue normally. Selector 11 remains explicit until native
  weekly-episode identity is modeled.
- Implemented service 76's named dialogue without a portrait, fixing Football
  Star scene 25011, PC 4303 and other group-speaker lines. Existing saves
  stopped there resume through the original dialogue reveal and input gates.
  Dialogue completion now also consumes the queued transition selector and
  its native random draw, shared with title/message panels.
- Restored the shared episode-intro and week-card screen, including Football
  Star's week titles: original fonts, background scaling, text placement,
  title wipe, background fade, subtitle animation and tap behavior. Save
  version 11 preserves intro animation state and migrates existing saves.
- Music now pauses with gameplay and resumes from the same position after
  closing the pause menu, regaining window focus, or returning to a live
  episode from the main menu.
- Restored native speaker-name widths, alignment and persistent spacing,
  including Howard's parents and quiz teachers. A shared glyph-bounds
  correction keeps names clear of dialogue and portraits across page turns.
  Save version 10 retains font history and migrates existing saves.
- Fixed top-left location/time labels so their text aligns inside the badge,
  including wrapped labels. No content reimport is needed.
- Restored eleven Android music cues that reuse another APK track at a
  specific start offset. This fixes missing-music warnings for 8202, 8208,
  8211, 8220, 8225 and the other verified redirects, using existing libraries.
- Implemented service 33's Instructions/message panel, fixing Football Star
  scene 25011, PC 629. Restored its original panel assets, reading delay and
  acknowledgement callback, including the shared random-stream side effect.
  Save version 9 preserves reading time and recovers older saves paused there.
- Relationship indicators now read the correct NPC property, so script changes
  update the icons and count, including Adam's four skulls in Football Star.
- Implemented service 39's dialogue panel cleanup, fixing the Football Star
  stop at scene 25013, PC 13. Saves paused there resume from their existing state.
- Fixed Football Star's word-grid tutorial initialization by matching the
  native word-list parser and accepting instruction pages with no targets and
  unused failure links. Playable-grid validation remains enforced.
- Restored the word-grid UI's original bitmap fonts, tutorial panels, portrait
  placement, time/score display, cloud borders and word prompts. Added native
  banner and panel motion, outgoing tile faces, and corrected hint/trace art.
  Save version 7 retains these animations and reads earlier saves.
- Restored Strength Up and other service-88 notifications with the original
  lettering, portrait-relative placement, rising letters and fade. Corrected
  their lifetime and dismissal on dialogue taps. The fix applies across
  episodes, and existing saves retain their remaining notice time.
- Restored football's original help panels, play legend, fonts, team/score HUD,
  four-step countdown, target motion and selection effects. Added smooth field
  movement and native localized result sequences with corrected feedback timing.
  Save version 8 preserves football animation state and reads earlier saves.

## v0.1.0

### Added

- Compatible KiWi engine that executes original scripts and imports resources
  locally from a player-supplied Android 1.0.9 APK and EXP episodes.
- Desktop launcher and main menu with persistent episode libraries, catalog
  grouping, manual saves and automatic checkpoints.
- Dialogue animation, portrait masks, choices, character selection,
  relationship indicators, and word, grid and football mini games.
- EXP, VM, engine-service and UI specifications documenting recovered behavior
  and remaining uncertainties.

### Known limitations

- Complete episode playback and full original-game fidelity remain in
  progress. Unsupported services stop explicitly with their pending arguments
  preserved.
- macOS builds use ad-hoc signing and are not notarized; Windows builds are
  unsigned.
