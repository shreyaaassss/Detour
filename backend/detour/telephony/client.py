from __future__ import annotations

import logging
from typing import Any

import httpx

from detour.voice.client import BASE, VoiceError

log = logging.getLogger("detour.telephony")


class Api:
    """The few ElevenLabs agent endpoints we use. Errors become VoiceError and never contain the key."""

    def __init__(self, api_key: str, http: httpx.Client | None = None, timeout: float = 20.0):
        self._http = http or httpx.Client(timeout=timeout)
        self._h = {"xi-api-key": api_key}

    def _do(self, method: str, path: str, **kw: Any) -> Any:
        try:
            r = self._http.request(method, f"{BASE}{path}", headers=self._h, **kw)
        except httpx.HTTPError as e:
            log.warning("elevenlabs %s %s: %s", method, path, type(e).__name__)
            raise VoiceError("Could not reach ElevenLabs.") from e
        if r.status_code >= 400:
            detail = ""
            try:
                detail = str(r.json().get("detail", ""))[:300]
            except ValueError:
                pass
            log.warning("elevenlabs %s %s -> %s %s", method, path, r.status_code, detail)
            raise VoiceError(f"ElevenLabs said {r.status_code}: {detail}".strip(": "), f"http_{r.status_code}")
        return r.json() if r.content else {}

    # --- a call -----------------------------------------------------------------------------------------
    def place_call(
        self,
        agent_id: str,
        phone_number_id: str,
        to_number: str,
        *,
        first_message: str,
        language: str,
        variables: dict[str, str],
        ring_seconds: int,
    ) -> tuple[str | None, str | None]:
        body = {
            "agent_id": agent_id,
            "agent_phone_number_id": phone_number_id,
            "to_number": to_number,
            "telephony_call_config": {"ringing_timeout_secs": ring_seconds},
            "conversation_initiation_client_data": {
                "dynamic_variables": variables,
                "conversation_config_override": {"agent": {"first_message": first_message, "language": language}},
            },
        }
        j = self._do("POST", "/v1/convai/twilio/outbound-call", json=body)
        if not j.get("success", True):
            raise VoiceError(str(j.get("message") or "The call could not be placed."), "call_failed")
        return j.get("conversation_id"), j.get("callSid")

    def signed_url(self, agent_id: str) -> str:
        """A short-lived address a browser can open a voice conversation with, without ever holding the API key."""
        j = self._do("GET", "/v1/convai/conversation/get-signed-url", params={"agent_id": agent_id})
        url = j.get("signed_url")
        if not url:
            raise VoiceError("ElevenLabs gave no address for the conversation.", "no_signed_url")
        return str(url)

    def conversation(self, conversation_id: str) -> dict[str, Any]:
        return self._do("GET", f"/v1/convai/conversations/{conversation_id}")

    # --- the agent and its tool (used by setup) --------------------------------------------------------------
    def create_tool(self, config: dict[str, Any]) -> dict[str, Any]:
        return self._do("POST", "/v1/convai/tools", json={"tool_config": config})

    def update_tool(self, tool_id: str, config: dict[str, Any]) -> dict[str, Any]:
        return self._do("PATCH", f"/v1/convai/tools/{tool_id}", json={"tool_config": config})

    def create_agent(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._do("POST", "/v1/convai/agents/create", json=body)

    def update_agent(self, agent_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._do("PATCH", f"/v1/convai/agents/{agent_id}", json=body)

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        return self._do("GET", f"/v1/convai/agents/{agent_id}")

    def phone_numbers(self) -> list[dict[str, Any]]:
        j = self._do("GET", "/v1/convai/phone-numbers")
        return j if isinstance(j, list) else []
