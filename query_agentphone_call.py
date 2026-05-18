"""Query an AgentPhone call by ID and print status/transcripts."""

from __future__ import annotations

import argparse
import json
from typing import Any

import requests

from config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch AgentPhone call details, including transcript if available")
    parser.add_argument("call_id", help="AgentPhone call ID, e.g. call_abc123")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not settings.agentphone_api_key:
        raise RuntimeError("AGENTPHONE_API_KEY is missing")

    url = f"{settings.agentphone_base_url.rstrip('/')}/v1/calls/{args.call_id}"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {settings.agentphone_api_key}"},
        timeout=20,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        print(f"AgentPhone GET failed: status={response.status_code} body={response.text}")
        raise exc

    data: dict[str, Any] = response.json() if response.content else {}
    if args.raw:
        print(json.dumps(data, indent=2, sort_keys=True))
        return

    print(f"id={data.get('id') or data.get('callId') or args.call_id}")
    print(f"status={data.get('status')}")
    print(f"direction={data.get('direction')}")
    print(f"startedAt={data.get('startedAt')}")
    print(f"endedAt={data.get('endedAt')}")
    print(f"durationSeconds={data.get('durationSeconds')}")

    transcripts = data.get("transcripts") or data.get("transcript") or []
    if isinstance(transcripts, str):
        print("transcripts:")
        print(f"- {transcripts}")
        return

    if not isinstance(transcripts, list) or not transcripts:
        print("transcripts: <none>")
        return

    print("transcripts:")
    for index, turn in enumerate(transcripts, 1):
        if isinstance(turn, dict):
            role = turn.get("role") or turn.get("speaker") or turn.get("source") or "unknown"
            transcript = turn.get("transcript") or turn.get("content") or turn.get("text") or ""
            response_text = turn.get("response")
            print(f"{index}. [{role}] {transcript}")
            if response_text:
                print(f"   response: {response_text}")
        else:
            print(f"{index}. {turn}")


if __name__ == "__main__":
    main()
