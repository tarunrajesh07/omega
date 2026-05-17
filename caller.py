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
            "initialGreeting": request.script,
            "systemPrompt": request.system_prompt,
            "metadata": {
                "event": request.event_type.value,
                "context": request.context,
            },
        }
        if self.settings.agentphone_voice:
            payload["voice"] = self.settings.agentphone_voice
        if self.settings.agentphone_from_number_id:
            payload["fromNumberId"] = self.settings.agentphone_from_number_id
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
        "You are Omega, the voice assistant for an autonomous vehicle ride. "
        f"You are speaking with {request.passenger_name}. "
        f"Current ride event and visual context: {request.context} "
        f"Your opening line has already been provided as the call's initial greeting: {request.script} "
        "After the greeting, continue naturally as a concise ride assistant. "
        "If the passenger asks where the vehicle is, restate the destination, nearby landmark, and any visual details from the context. "
        "If they ask what to do next, tell them to look for the vehicle at the described pickup spot and confirm you can wait briefly. "
        "Do not proactively suggest rerouting. If the passenger asks to reroute or asks for a different pickup location, say: Got it, I can reroute there. That will add about two minutes to your ETA. "
        "If they ask for a delay, cancellation, or safety status, answer directly using only the available context; do not invent exact street names, ETAs, or vehicle details. "
        "Keep responses to one or two short sentences unless the passenger asks for more detail."
    )
