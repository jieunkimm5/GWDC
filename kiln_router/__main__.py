"""Local setup check; does not call any model API."""

import sys


def main() -> None:
    print(f"kiln_router: Python {sys.version.split()[0]}")
    print("Setup ready. Use KilnRouter(client).recommend_route(task).")
    print("No API call was made.")


if __name__ == "__main__":
    main()
