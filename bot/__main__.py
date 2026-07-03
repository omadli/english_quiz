"""Placeholder bot process for Phase 0.

Phase 1 replaces this with the aiogram dispatcher. For now it only
verifies the container builds and stays running.
"""

import time


def main() -> None:
    print("bot stub: Phase 0 placeholder — aiogram wiring lands in Phase 1", flush=True)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
