# ctl/__main__.py
import sys


def _cmd_help(args: list[str]) -> int:
    print("hello world")
    return 0


_COMMANDS: dict[str, tuple[callable, str]] = {
    "help": (_cmd_help, "show this message"),
}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print("Usage: hiddenctl <command>", file=sys.stderr)
        print("Run 'hiddenctl help' for available commands.", file=sys.stderr)
        return 1

    command, *args = argv

    if command not in _COMMANDS:
        print(f"Unknown command: {command!r}", file=sys.stderr)
        print("Run 'hiddenctl help' for available commands.", file=sys.stderr)
        return 2

    handler, _ = _COMMANDS[command]
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
