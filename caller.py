"""AgentPhone outbound call integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import requests

from config import Settings
from models import CallRequest, CallResult

logger = logging.getLogger(__name__)


@dataclass
class AgentPhoneCaller:
    settings: Settings

    async def call(self, request: CallRequest) -> CallResult:
        missing = self.settings.missing_for_live_calls()
        if missing:
            logger.info("Would call %s: %s", request.to_number or "<missing number>", request.script)
            return CallResult(
                attempted=False,
                call_id=None,
                message=f"Dry run call logged; missing {', '.join(missing)}.",
            )

        payload = {
            "agentId": self.settings.agentphone_agent_id,
            "toNumber": request.to_number,
            "metadata": {
                "event": request.event_type.value,
                "context": request.context,
            },
            "initialMessage": request.script,
            "systemPrompt": request.system_prompt,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.agentphone_api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = await asyncio.to_thread(
                requests.post,
                f"{self.settings.agentphone_base_url.rstrip('/')}/v1/calls",
                json=payload,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("AgentPhone call request failed: %s", exc)
            return CallResult(attempted=True, call_id=None, message=f"AgentPhone request failed: {exc}")

        data: dict[str, Any] = response.json() if response.content else {}
        call_id = data.get("id") or data.get("callId")
        logger.info("AgentPhone call started: %s", call_id or data)
        return CallResult(attempted=True, call_id=call_id, message="Outbound call started.")


def build_system_prompt(request: CallRequest) -> str:
    return (
        f"You are the voice assistant for an autonomous vehicle. The passenger is {request.passenger_name}. "
        f"You are calling about this event: {request.context}. Start with: {request.script} "
        "Answer questions briefly and clearly. If the passenger asks for an action, confirm it in one sentence."
    )

