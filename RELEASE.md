# v0.4.0

## Fixed

- Fix Windows desktop builds stopping with `libgcc not found` while preparing
  RAR import support.
- Recognize classroom-quiz answer feedback in Choice hints, including Football
  Star's shuffled questions and finals. Correct answers turn green and wrong
  answers red without changing grades, timers, audio or saved state.
- Keep scene captions such as Football Star's “Before School” inside the
  badge, using the native 14-point Arial region for IPA fonts in both games.
  Substitute fonts fit the same region; Android bitmap labels retain their
  original layout rules.
- Restore the held gear highlight, release-to-open behavior, 400 ms pause-menu
  expansion and original pause/menu click sounds in both games. Dragging off
  cancels the press; the entrance freezes story clocks and gates menu input.
- Highlight held menu rows and choices until release, canceling when dragged
  away or when the question changes. Preserve the Pause menu's side borders
  instead of stretching row backgrounds over them, in both games.
- Apply Choice hints to timed word quizzes and deferred rewards across short
  choice sequences, including Football Star's Beth conversation. Compare
  matching later answers without changing the live story or guessing scores.
- Restore solid word-grid tiles, rotating side/back faces, shine frames and
  shattering fragments followed by tile pops. Native fragment RNG draws and
  active effects survive save/load; older saves migrate without replaying play.
- Speed up iOS football by reusing sprite images and scaling them in the native
  renderer. Restore SHS's original You–Opp score strip and bitmap lettering.
  Game timing, scoring and target input remain unchanged.
- Batch word-grid tile projection in the iOS renderer and cache tile artwork,
  avoiding hundreds of image-strip commands per frame. Timed word choices
  also benefit from the shared scaling and text-baseline fixes.
- Keep glyph baselines aligned at half-pixel origins, fixing raised letters
  such as the “i” in Continue across dialogue and choices in both games.
- Restore the bottom “Touch the screen to continue” instruction in dialogue.
- Use the original Pause menu's artwork and Resume, Options, Help & About and
  Main Menu entries. Manual Save/Load is available in paused Options; timers
  remain paused while browsing those pages.
- Make iOS safe areas and letterboxing black, including the top and bottom
  margins around the game.
- Restore CoD's original menu click sound, respecting the Sound setting
  independently of Music.
- Play the original SHS and CoD main-menu themes on desktop and iOS. Menu
  music respects Music/focus settings and preserves the paused story stream.
- Restore the original dialogue Continue tab in both games, with supplied
  theme artwork and its 250 ms expansion after text finishes. Older saves
  migrate without replaying the story.
- Allow opaque files in the iOS Files picker so IPA/EXP/ZIP selection does
  not depend on a provider identifying their type before the first opening.
  The shared importer continues to validate the selected content.

## Added

- Optional **Options → Cheats → Choice hints** colors recognized near-term
  score/relationship gains or correct quiz answers green, losses/wrong answers
  or alternatives without a recognized gain red, and mixed effects amber.
  Unknown effects retain the normal style.
  The preview leaves the live story, timers, random state and saves untouched.
- Import RAR4/RAR5 episode collections on desktop and iOS, with nested EXPs,
  catalogs, duplicate detection and atomic publication. Password-protected and
  unsupported archive variants report an error.
- Show the runtime version and a clickable GitHub project link in Help/About,
  opened with the main menu's info icon.
- Import ZIP collections of EXP episodes on desktop and iOS, including nested
  folders and SHS/CoD catalogs. Episodes persist in the library without the
  source ZIP; repeated imports preserve existing episodes and saved progress.
- An iPhone/iPad app sharing the Python engine, importers, menus and game
  renderers with desktop. Native iOS drawing, fonts, audio, touch, keyboard
  and Files access support SHS/CoD libraries and existing save formats.
  Backgrounding pauses playback and checkpoints progress. The Xcode project
  supports device signing; CI produces an unsigned IPA and checksum for
  users to sign and install. See [iOS setup](docs/IOS_APP.md).

## Changed

- Replace More EA Games with **Switch Game**, preserving the original menu
  artwork, lettering and animation. Switching checkpoints the current story
  and opens the other installed game, or the chooser if it is not installed.
