"""Import, inspect and launch player-supplied SHS content."""

import argparse
import logging
import sys

from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="shs-tool",
        description="Inspect EXP files and play supported SHS scripts with your own game data.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG).",
    )
    subparsers = parser.add_subparsers(dest="command")

    trace_parser = subparsers.add_parser(
        "trace", help="Execute KiWi to the first pending action and print a JSON trace.",
    )
    trace_parser.add_argument("archive", type=Path, help="Path to the .exp archive.")
    trace_parser.add_argument("--max-steps", type=int, default=100_000)
    trace_parser.add_argument("--max-events", type=int, default=10_000)

    import_parser = subparsers.add_parser("import", help="Create a local library from your APK or IPA and episode files.")
    source = import_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--apk", type=Path, help="Your SHS Android 1.0.9 APK.")
    source.add_argument("--ipa", type=Path, help="Your SHS IPA with compatible game assets.")
    import_parser.add_argument("--episodes", type=Path, nargs="+", action="extend", default=[],
                               help="EXP files or directories; directories are scanned recursively.")
    import_parser.add_argument("--library", type=Path, default=Path(".shs-library"),
                               help="New library directory (default: .shs-library).")

    list_parser = subparsers.add_parser("list", help="List episodes in a local content library.")
    list_parser.add_argument("--library", type=Path, default=Path(".shs-library"))

    play_parser = subparsers.add_parser("play", help="Open the main menu, or start a selected episode.")
    play_parser.add_argument("--library", type=Path, help="Content library; defaults to the existing local library or user application data.")
    play_parser.add_argument("--episode", help="Start directly: unique ID prefix, filename, or title from list.")
    saves = play_parser.add_mutually_exclusive_group()
    saves.add_argument("--resume", action="store_true", help="Load this episode's local save slot.")
    saves.add_argument("--load", type=Path, help="Load a specific runtime JSON save.")
    play_parser.add_argument("--no-audio", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Configure logging
    log_level = logging.WARNING
    if args.verbose >= 2:
        log_level = logging.DEBUG
    elif args.verbose >= 1:
        log_level = logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    if args.command in ("import", "list", "play"):
        from .content import ContentError, ContentLibrary, import_game
        from .runtime import SaveError
        from .vm import VMError

        try:
            if args.command == "import":
                manifest = import_game(args.apk or args.ipa, args.episodes, args.library)
                print(f"Imported {len(manifest['episodes'])} episodes into {args.library}")
                return
            if args.command == 'play':
                if (args.load or args.resume) and not args.episode:
                    parser.error('--load and --resume require --episode; omit them to use the main menu')
                try:
                    from .application import Application
                except ModuleNotFoundError as error:
                    if error.name != 'pygame':
                        raise
                    parser.error('Desktop support is not installed. Run uv sync --extra desktop '
                                 'or install the package with its [desktop] extra.')
                app = Application(args.library, audio=not args.no_audio)
                try:
                    if args.episode:
                        if not app.library:
                            raise ContentError(app.message or 'Import your APK or IPA before selecting an episode')
                        app.selected = app.library.select(args.episode)['id']
                        app.start(resume=args.resume, load_path=args.load)
                except Exception:
                    app.close()
                    raise
                app.run()
                return
            with ContentLibrary(args.library) as library:
                library.ensure_builtin_episodes()
                if args.command == "list":
                    for record in library.episodes:
                        print(f"{record['id'][:12]}  {record['titles'][0]}  ({record['name']})")
                    return
        except (ContentError, SaveError, VMError, OSError) as error:
            parser.error(str(error))

    elif args.command == "trace":
        import json
        from .trace import trace_archive

        try:
            result = trace_archive(args.archive, max_steps=args.max_steps, max_events=args.max_events)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result["status"] in ("vm_error", "missing_script"):
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)
