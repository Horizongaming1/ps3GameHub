#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from urllib import request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a cache job via PS3 Cache API")
    parser.add_argument("--api-url", default="http://localhost:8087", help="Base API URL")
    parser.add_argument("--game-id", type=int, required=True, help="Game ID from GET /games")
    parser.add_argument("--target-id", type=int, required=True, help="Target ID from GET /targets")
    parser.add_argument("--auto-mount", action="store_true", help="Trigger webMAN mount after upload")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = {
        "game_id": args.game_id,
        "target_id": args.target_id,
        "auto_mount": args.auto_mount,
    }

    req = request.Request(
        url=f"{args.api_url.rstrip('/')}/jobs/cache",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=10) as response:  # noqa: S310
            body = response.read().decode("utf-8")
            print(body)
            return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Request failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
