from __future__ import annotations

import hmac
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from detour.telephony.client import Api
from detour.telephony.config import CallSettings, mask
from detour.telephony.convo import Reading, read_conversation
from detour.voice.client import VoiceError

log = logging.getLogger("detour.telephony")
POLL_SECONDS = 1.0

Deliver = Callable[[Callable[[], None]], None]  # runs a function on the app's own thread


class CallRun:
    """One phone call: which events it has already told the app about, and what to tell it next."""

    def __init__(self, offer_id: str):
        self.offer_id = offer_id
        self.sent_answered = False
        self.finished = False

    def next_events(self, r: Reading, waited: float, ring_limit: float) -> list[tuple[str, str | None]]:
        out: list[tuple[str, str | None]] = []
        if r.answered and not self.sent_answered:
            self.sent_answered = True
            out.append(("answered", None))
        if r.decision is not None:
            out.append((r.decision, r.how))
            self.finished = True
        elif r.state == "ended":
            out.append(("unclear" if r.answered else "no_answer", None))
            self.finished = True
        elif not r.answered and waited > ring_limit + 5:  # the app's own ring timer normally ends it first
            out.append(("no_answer", None))
            self.finished = True
        return out


class TelephonyService:
    """Places the escalation call and reports its outcome back to the rescue flow."""

    def __init__(self, settings: CallSettings, api: Api | None = None, deliver: Deliver | None = None):
        self.s = settings
        self.api = api or (Api(settings.api_key) if settings.api_key else None)
        self.deliver: Deliver = deliver or (lambda fn: fn())
        self.placed = 0
        self.history: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    # --- can we call? -----------------------------------------------------------------------------------------
    def ready(self) -> bool:
        return not self.s.missing()

    def can_call(self, driver: str | None) -> tuple[bool, str]:
        miss = self.s.missing()
        if miss:
            return False, "not set up: " + ", ".join(miss)
        if not self.s.phone_for(driver):
            return False, f"no number is listed for {driver}"
        if self.placed >= self.s.max_calls:
            return False, f"the limit of {self.s.max_calls} calls for this run was reached"
        return True, ""

    def language_for(self, driver_language: str) -> str:
        return driver_language if self.s.language == "driver" else self.s.language

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.s.enabled,
            "ready": self.ready(),
            "missing": self.s.missing(),
            "language": self.s.language,
            "numbers": {k: mask(v) for k, v in self.s.phones.items()},
            "placed": self.placed,
            "limit": self.s.max_calls,
            "public_url_set": bool(self.s.public_url),
            "recent": self.history[-6:],
        }

    # --- placing a call ---------------------------------------------------------------------------------------------
    def start(
        self,
        offer_id: str,
        driver: str | None,
        *,
        script: str,
        language: str,
        variables: dict[str, str],
        ring_seconds: int,
        on_event: Callable[[str, str, str | None], None],
        is_open: Callable[[], bool],
    ) -> bool:
        """Place the call on a background thread and report what happens. Returns False if it was not allowed."""
        ok, why = self.can_call(driver)
        number = self.s.phone_for(driver)
        if not ok or number is None or self.api is None or self.s.agent_id is None or self.s.phone_number_id is None:
            self._note(offer_id, "skipped", why)
            return False
        with self._lock:
            self.placed += 1
        threading.Thread(
            target=self._run,
            daemon=True,
            args=(offer_id, number, script, language, variables, ring_seconds, on_event, is_open),
        ).start()
        return True

    def _note(self, offer_id: str, what: str, detail: str = "") -> None:
        self.history.append({"offer": offer_id, "what": what, "detail": detail, "at": time.time()})

    def _run(self, offer_id, number, script, language, variables, ring_seconds, on_event, is_open) -> None:
        assert self.api and self.s.agent_id and self.s.phone_number_id
        send = lambda outcome, how=None: self.deliver(lambda: on_event(offer_id, outcome, how))  # noqa: E731
        try:
            cid, sid = self.api.place_call(
                self.s.agent_id,
                self.s.phone_number_id,
                number,
                first_message=script,
                language=language,
                variables={**variables, "offer_id": offer_id},
                ring_seconds=ring_seconds,
            )
        except VoiceError as e:
            self._note(offer_id, "failed", e.message)
            send("no_answer")
            return
        self._note(offer_id, "placed", f"to {mask(number)} conversation {cid}")
        if not cid:
            return
        run = CallRun(offer_id)
        started = time.time()
        while not run.finished and is_open():
            time.sleep(POLL_SECONDS)
            try:
                reading = read_conversation(self.api.conversation(cid))
            except VoiceError:
                continue  # a missed poll is fine; the app's own timers still apply
            for outcome, how in run.next_events(reading, time.time() - started, ring_seconds):
                send(outcome, how)
        self._note(offer_id, "ended")

    # --- the agent's tool calls us --------------------------------------------------------------------------------
    def check_secret(self, given: str | None) -> bool:
        return bool(self.s.secret) and bool(given) and hmac.compare_digest(self.s.secret, given or "")
