import argparse
import discord_http
import platform
import sys

from importlib.metadata import version


def get_package_version(name: str) -> str:
    try:
        output = version(name)
        if not output.lower().startswith("v"):
            output = f"v{output}"
        return output
    except Exception:
        return "N/A (not installed?)"


def show_version() -> None:
    pyver = sys.version_info

    container = [
        f"python       v{pyver.major}.{pyver.minor}.{pyver.micro}-{pyver.releaselevel}",
        f"discord.http v{discord_http.__version__}",
        f"quart        {get_package_version('quart')}",
        f"system_info  {platform.system()} {platform.release()} ({platform.version()})",
    ]

    print("\n".join(container))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="discord.http",
        description="Command-line tool to debug"
    )

    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="Show relevant version information"
    )

    args = parser.parse_args()

    if args.version:
        show_version()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
