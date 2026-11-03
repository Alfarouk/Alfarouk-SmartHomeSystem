"""Explicit model download command for the optional face-comparison feature."""
import argparse
from pathlib import Path
import sys

from .face import download_models
from .controller import CommandError


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and verify pinned OpenCV face models")
    parser.add_argument("directory", type=Path, nargs="?", default=Path("models"))
    args = parser.parse_args()
    try:
        download_models(args.directory)
        print(f"Verified face models in {args.directory}")
        return 0
    except (CommandError, OSError) as e:
        print(f"Face model setup failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
