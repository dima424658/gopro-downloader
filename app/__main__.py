"""Application entry point for GoPro Downloader."""

from . import create_app
from .window import run_desktop


def main() -> None:
    run_desktop(create_app())


if __name__ == "__main__":
    main()
