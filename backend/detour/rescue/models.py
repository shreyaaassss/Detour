from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

State = Literal[
    "REPORTED",
    "DRIVER_CONFIRMED",
    "AWAITING_HEAD",
    "HEAD_APPROVED",
    "OFFER_PUSHED",
    "CALL_ESCALATED",
    "CANDIDATE_DECLINED",
    "ACCEPTED",
    "COMMITTED",
    "HEAD_TIMEOUT",
    "EXHAUSTED",
    "CANCELLED",
    "REJECTED",
]
TERMINAL: set[str] = {"COMMITTED", "EXHAUSTED", "CANCELLED", "REJECTED"}
OFFERING: set[str] = {"OFFER_PUSHED", "CALL_ESCALATED", "ACCEPTED"}  # a vehicle is reserved in these states


class Candidate(BaseModel):
    vehicle_id: str
    driver: str | None
    feasible: bool
    reason: str | None = None  # why not, in plain language
    reach_site: float | None = None  # when it gets to the broken-down van
    leave_site: float | None = None  # when it leaves after the handover
    delivery_time: float | None = None  # when the main parcel would be delivered
    own_delay: float | None = None  # the most it delays its own remaining deliveries, in minutes
    impact: dict[str, int] | None = None  # kept / moved / broken / new versus the current plan
    other_changes: list[dict[str, str]] = Field(default_factory=list)  # other deliveries that change
    rank: int | None = None


class Proposal(BaseModel):
    vehicle_id: str
    location_id: str
    failure_time: float
    primary: str | None  # the parcel the rescue is built around
    primary_place: str | None
    primary_due: float | None
    parcels: list[str]  # everything still on the broken vehicle
    plan_version: int
    candidates: list[Candidate]

    @property
    def feasible(self) -> list[Candidate]:
        return [c for c in self.candidates if c.feasible]


class HistoryItem(BaseModel):
    wall: float
    sim: float | None
    state: str
    note: str = ""


class Incident(BaseModel):
    id: str
    driver: str
    vehicle_id: str
    language: str
    transcript: str
    source: Literal["text", "voice", "buttons"] = "text"
    location_id: str | None = None
    location_name: str | None = None
    state: State
    note: str = ""  # why it was rejected or cancelled
    known_locations: list[dict[str, str]] = Field(default_factory=list)  # offered when the place is unknown
    readback: dict[str, str] = Field(default_factory=dict)
    parcels: list[str] = Field(default_factory=list)
    primary: str | None = None
    failure_time: float | None = None
    proposal: Proposal | None = None
    approver_role: Literal["head", "backup"] = "head"
    approved_by: str | None = None
    approved_version: int | None = None
    shortlist: list[str] = Field(default_factory=list)
    current: int = -1
    claim: dict[str, Any] | None = None
    confirm_deadline: float | None = None
    head_deadline: float | None = None
    reprompts: int = 0
    escalated_to_dispatcher: bool = False
    result: str | None = None  # a one-line outcome for the screens
    history: list[HistoryItem] = Field(default_factory=list)


class Offer(BaseModel):
    id: str
    incident_id: str
    index: int
    vehicle_id: str
    driver: str | None
    channel: Literal["push", "call"]
    sent: float
    deadline: float  # when the push times out (push) or the ring times out (call)
    status: Literal["open", "accepted", "declined", "timed_out", "closed"] = "open"
    outcome: str | None = None
    closed: float | None = None
    call_state: Literal["ringing", "in_call"] | None = None
    conversation_deadline: float | None = None
    ambiguous: int = 0
    text: dict[str, str] = Field(default_factory=dict)
    script: dict[str, str] = Field(default_factory=dict)
    language: str = "en"


class Notification(BaseModel):
    id: int
    to: str  # driver:<name>, role:head, role:backup or role:dispatcher
    kind: str
    incident_id: str | None = None
    text: dict[str, str]
    wall: float
    sim: float | None = None
    data: dict[str, Any] = Field(default_factory=dict)
