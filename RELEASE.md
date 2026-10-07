# v0.4.2

## Added

- Check for newer public releases once per launch on desktop and iOS, with a
  persistent **Options → Update checks** switch shared by both games. A newer
  release shows “Update available. Download here.” using the game's Yes/No
  menu skin; Yes opens its GitHub release page and No dismisses it for this
  launch. Checks run in the background, fail quietly offline, and wait for a
  menu before showing the prompt during play.

## Fixed

- Honor the script's music repeat flag on desktop and iOS. Repeating CoD
  story tracks keep playing; one-shot cues and the native CoD menu theme
  still finish normally. Pause/resume preserves the repeat setting.
- Restore the original iOS dialogue-box entrance for portrait speakers in
  both games: 120 ms from the portrait to a narrow strip, then 200 ms to full
  height. Keep the common layout and fixed-size border pieces. Save/load
  preserves an entrance in progress; older saves retain their full-size box.
- Complete the recovered dialogue lifecycle for SHS and CoD: grow narration
  from the retained portrait position, clip only the outer portrait frame at
  box completion, and use the native shake hold, scale and rotation timing.
  Early reveal taps settle the box/name while portrait animation continues.
- Restore neutral speaker entrances and delayed expression crossfades. Reuse
  speaker state across choices, and clear expression caches at native scene
  boundaries. Save version 21 preserves these states; older saves remain
  readable without replaying their current dialogue.
- Give iOS simulator installation its own five-minute timeout in CI, with
  progress output and diagnostics, so slow installs can finish after boot
  without consuming the app's verification time.
- Report the release version in macOS app metadata and direct Xcode builds,
  matching the runtime's Help/About version.
