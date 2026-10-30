#!/usr/bin/env python3
"""Run the maintained browser regression against the isolated Docker test stack.

Start the stack documented in QUICKSTART.md first. A failed assertion or browser
error exits nonzero; no fixed sleeps or success-by-printing are used.
"""

import subprocess
from pathlib import Path


def main():
    subprocess.run(
        ["npm", "run", "test:e2e"],
        cwd=Path(__file__).resolve().parents[1] / "frontend",
        check=True,
    )


if __name__ == "__main__":
    main()
