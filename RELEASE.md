# v0.3.0

**Renamed from shs-runtime to exp-runtime**

- Added SHS service 15 named dialogue, used in 62 of the supplied episodes,
  plus native completions for services 14/21. Existing stopped saves resume
  in place with both APK and IPA libraries; no episode reimport is needed.
- Fixed CoD service 100 stops, including What Happened to Colt, Part 2 at
  scene 25001 / PC 5375. Promotional-link calls follow the supplied native
  runtime's local completion and continue the script. Existing stopped saves
  resume without reimporting episodes or restarting them.
- CoD episode imports now read `cod_options.sav` for original volume/category
  names; SHS uses the same matching and update behavior with `shs_options.sav`
  for both APK and IPA libraries. Add the catalog or reimport
  your episode folder to update existing groups. Identical EXPs are deduplicated
  in both games, including renamed copies, while saves remain intact. Stories
  absent from the supplied catalog retain numeric pack headers.
- Added a kiwi fruit logo to the game chooser and app icons, with an editable
  SVG source shared by the desktop builds.
- Added CoD build/platform queries using the imported IPA's version; the
  desktop reports its store as unavailable. Legacy services 94/96 complete
  with their native zero result. Older saves stopped at these calls can resume.
- Corrected IPA dialogue formatting in **both games** using Ghidra-verified
  native rules. Long names wrap into the taller header at their original size,
  including overlap across the box border. Body text keeps its own position
  and page capacity. The fix applies generally, including substitute fonts;
  existing IPA saves reflow at their saved reading position without replaying.
- Corrected CoD's normal speech colors to **dark-red names and black dialogue**,
  matching the supplied original-game screenshots and native font palette.
- **SHS and CoD** share the **v0.1.3 SHS dialogue skin** and common renderer,
  with each game's artwork and verified bitmap/outline font rules. No reimport
  is needed.
- **EXP Runtime** now offers **Surviving High School** and **Cause of Death**
  in the launcher. Supply assets for each game separately, then add its EXPs.
  Use **Options → Switch Game** to checkpoint progress and return to the chooser.
- Import a compatible **CoD IPA**, including **Volume One**. CoD uses its own
  art, UI strings, bundled/system fonts, relationship IDs and nine music tracks.
  Named dialogue is supported; ad requests complete locally without a network
  request. Unknown services remain explicit stops.
- Game-specific code lives in `exp_runtime/shs/` and `exp_runtime/cod/`, sharing
  the KiWi VM, EXP parser, common panels, saves and launcher.
- The primary commands are `exp-runtime` and `exp-tool`; `shs` and `shs-tool`
  remain aliases. Existing SHS libraries and saves still load, and prior library
  locations are discovered without moving files. New libraries record the game
  explicitly and never borrow another game's assets.

CoD support is initial: its Volume One opening, save restoration and all nine
base music sources have been checked. Complete episode routes and full native
visual/timing parity remain unverified. See [CoD support](docs/COD.md) for
known limits. No original game content is included in downloads.
