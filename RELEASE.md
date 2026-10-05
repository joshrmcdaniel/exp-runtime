# Unreleased

## Added

- Import an SHS IPA through setup, drag-and-drop, or `shs-tool import --ipa`,
  including its bundled episodes and Football Star. IPA import checks the SHS
  bundle identifier and required assets, without requiring a specific version,
  build number or executable.
- IPA playback reads its original UI artwork, timer wedges, name-entry panel
  and football graphics. It uses original installed fonts when available and
  falls back to the system default when they are missing.
- Optionally add your Android 1.0.9 APK to supply missing IPA music, during
  import with `--music-apk` or later through **Add APK Music** / `shs-tool add-music`.
  IPA assets and installed original fonts retain priority. Existing IPA saves
  and live story progress remain compatible.

## Compatibility

- Existing Android libraries and saves remain supported. IPA libraries have
  separate content identities; Android saves cannot be transferred to them.
- System-font rendering can differ from iOS and affect text layout.
- The inspected IPA contains ten playable music tracks but omits another ten
  that the original app downloaded separately. This leaves The New Girl's
  opening music silent with the IPA alone; the optional APK supplies those
  tracks. Other missing assets and iOS download-cache import remain unsupported.
  Libraries with supplemental music require this runtime's manifest version 3.
  See [IPA support](docs/IPA.md) for the native evidence,
  validation coverage and current limits.
