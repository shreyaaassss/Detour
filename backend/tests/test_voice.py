import os

import httpx
import pytest
from fastapi.testclient import TestClient

from detour.api import create_app
from detour.voice.client import ElevenLabs, VoiceError
from detour.voice.service import VoiceService, from_env
from detour.voice.warm import demo_lines, warm

AUDIO = b"ID3" + b"\x00" * 900  # stands in for an mp3 or a recording


class Fake:
    """A stand-in for the ElevenLabs HTTP API that records every call and can be told to fail."""

    def __init__(self, status=200, transcript="My truck broke down near Hadapsar", lang="eng"):
        self.calls: list[httpx.Request] = []
        self.status, self.transcript, self.lang = status, transcript, lang

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"detail": "nope"})
        if "/text-to-speech/" in request.url.path:
            return httpx.Response(200, content=AUDIO + request.content[-8:], headers={"character-cost": "2"})
        if request.url.path.endswith("/speech-to-text"):
            return httpx.Response(200, json={"text": self.transcript, "language_code": self.lang})
        if request.url.path.endswith("/subscription"):
            return httpx.Response(200, json={"character_count": 7, "character_limit": 125809})
        return httpx.Response(404)

    @property
    def tts_calls(self):
        return [c for c in self.calls if "/text-to-speech/" in c.url.path]


def client(fake: Fake, **kw) -> ElevenLabs:
    return ElevenLabs("secret-key", http=httpx.Client(transport=httpx.MockTransport(fake)), **kw)


def service(fake: Fake, tmp_path=None, **kw) -> VoiceService:
    return VoiceService(client(fake), tmp_path, **kw)


# --- the ElevenLabs client ---
def test_speech_request_shape():
    fake = Fake()
    sp = client(fake, tts_model="eleven_v4_turbo").tts("Hello", "VOICE1")
    req = fake.tts_calls[0]
    assert req.url.path == "/v1/text-to-speech/VOICE1" and req.headers["xi-api-key"] == "secret-key"
    assert b'"model_id":"eleven_v4_turbo"' in req.content.replace(b" ", b"") and b"Hello" in req.content
    assert sp.cost == 2 and sp.audio.startswith(b"ID3")


@pytest.mark.parametrize(
    ("ctype", "ext"),
    [("audio/webm;codecs=opus", "webm"), ("audio/mp4", "m4a"), ("audio/ogg", "ogg"), ("audio/wav", "wav"), ("", "bin")],
)
def test_transcription_names_the_file_so_it_is_understood(ctype, ext):
    fake = Fake(transcript="  hello  ", lang="hin")
    tr = client(fake).stt(AUDIO, ctype)
    body = fake.calls[0].content
    assert f'filename="report.{ext}"'.encode() in body and b"scribe_v1" in body
    assert (tr.text, tr.language) == ("hello", "hin")


@pytest.mark.parametrize(
    ("status", "code"), [(401, "voice_key_refused"), (429, "voice_quota"), (500, "voice_unavailable")]
)
def test_failures_become_voice_errors_without_leaking_the_key(status, code):
    with pytest.raises(VoiceError) as e:
        client(Fake(status=status)).tts("Hello", "V")
    assert e.value.code == code and "secret-key" not in e.value.message
    with pytest.raises(VoiceError):
        client(Fake(status=status)).stt(AUDIO, "audio/webm")


def test_a_network_failure_is_a_voice_error():
    def boom(request):
        raise httpx.ConnectError("down")

    c = ElevenLabs("k", http=httpx.Client(transport=httpx.MockTransport(boom)))
    with pytest.raises(VoiceError):
        c.tts("Hi", "V")
    with pytest.raises(VoiceError):
        c.stt(AUDIO, "audio/webm")


# --- the cache and the spending cap ---
def test_a_sentence_is_paid_for_once(tmp_path):
    fake = Fake()
    v = service(fake, tmp_path)
    a = v.speak("Breakdown at Hadapsar.", "en")
    b = v.speak("Breakdown at Hadapsar.", "en")
    assert (
        a == b
        and len(fake.tts_calls) == 1
        and v.spent == len("Breakdown at Hadapsar.")
        and (v.hits, v.misses) == (1, 1)
    )
    # a new run (a fresh service on the same folder) still finds it on disk
    again = service(Fake(), tmp_path)
    assert again.speak("Breakdown at Hadapsar.", "en") == a and again.spent == 0


def test_a_different_voice_or_text_is_a_different_sentence(tmp_path):
    fake = Fake()
    v = VoiceService(client(fake, voices={"hi": "HINDI_VOICE"}), tmp_path)
    v.speak("Hello", "en")
    v.speak("Hello", "hi")  # another voice
    v.speak("Hello there", "en")
    assert len(fake.tts_calls) == 3
    assert {c.url.path.rsplit("/", 1)[1] for c in fake.tts_calls} == {"Xb7hH8MSUJpSbSDYk0k2", "HINDI_VOICE"}


def test_the_budget_stops_spending_but_cached_lines_still_play(tmp_path):
    fake = Fake()
    v = service(fake, tmp_path, budget_chars=30)
    v.speak("0123456789", "en")  # 10
    v.speak("abcdefghij", "en")  # 20
    with pytest.raises(VoiceError) as e:
        v.speak("this one is too much for it", "en")
    assert e.value.code == "voice_budget" and len(fake.tts_calls) == 2
    assert v.speak("0123456789", "en")  # already paid for, so free


def test_one_long_message_is_refused(tmp_path):
    with pytest.raises(VoiceError) as e:
        service(Fake(), tmp_path, max_chars=20).speak("x" * 21, "en")
    assert e.value.code == "voice_too_long"


def test_a_failed_synthesis_costs_nothing_and_is_not_cached(tmp_path):
    v = service(Fake(status=500), tmp_path)
    with pytest.raises(VoiceError):
        v.speak("Hello", "en")
    assert v.spent == 0 and v.errors == 1 and not list(tmp_path.glob("*.mp3"))


def test_concurrent_requests_for_the_same_line_pay_once(tmp_path):
    import threading

    fake = Fake()
    v = service(fake, tmp_path)
    threads = [threading.Thread(target=lambda: v.speak("Same line", "en")) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(fake.tts_calls) == 1


def test_without_a_key_voice_is_simply_off():
    v = from_env({}, None)
    assert not v.enabled
    with pytest.raises(VoiceError) as e:
        v.speak("Hi", "en")
    assert e.value.code == "voice_off"
    assert not from_env({"ELEVENLABS_API_KEY": "k", "DETOUR_VOICE": "off"}, None).enabled
    on = from_env({"ELEVENLABS_API_KEY": "k", "ELEVENLABS_VOICE_MR": "MR1", "DETOUR_VOICE_BUDGET": "500"}, None)
    assert on.enabled and on.client.voice_for("mr") == "MR1" and on.client.voice_for("en") != "MR1" and on.budget == 500


def test_status_never_contains_the_key_and_never_waits_for_elevenlabs(tmp_path):
    import time

    slow = Fake()
    orig = slow.__call__

    def slow_call(request):
        if request.url.path.endswith("/subscription"):
            time.sleep(0.4)
        return orig(request)

    v = service(Fake(), tmp_path)
    v.client = client(type("S", (), {"__call__": staticmethod(slow_call)})())  # a balance lookup that takes 0.4 s
    t0 = time.time()
    st = v.status()
    assert time.time() - t0 < 0.2, "the screen waited for the credit count"
    assert st["enabled"] and st["account"] is None and st["budget"]["limit"] == 20000
    deadline = time.time() + 3
    while v.status()["account"] is None and time.time() < deadline:
        time.sleep(0.05)
    assert v.status()["account"] == {"used": 7, "limit": 125809}
    assert "secret-key" not in str(st)


# --- through the API ---
@pytest.fixture
def rig(tmp_path):
    fake = Fake()
    app = create_app(None, start_ticker=False, voice=service(fake, tmp_path / "audio"))
    return TestClient(app), fake, app


def report(c, **kw):
    return c.post(
        "/incidents/report", json={"driver": "Ravi", "transcript": "My truck broke down near Hadapsar", **kw}
    ).json()["incident"]


def test_the_system_speaks_what_it_produced_and_nothing_else(rig):
    c, fake, _ = rig
    inc = report(c)
    r = c.get("/voice/audio", params={"what": "readback", "ref": inc["id"], "lang": "mr"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content.startswith(b"ID3")
    sent = fake.tts_calls[0].content.decode()
    assert "हडपसर" in sent  # the Marathi read-back, with the place in Devanagari
    c.get("/voice/audio", params={"what": "readback", "ref": inc["id"], "lang": "mr"})
    assert len(fake.tts_calls) == 1  # the second play came from the cache
    # there is no way to ask it to say something of your own
    assert c.get("/voice/audio", params={"what": "text", "ref": "buy bitcoin", "lang": "en"}).status_code == 422
    assert c.get("/voice/audio", params={"what": "readback", "ref": "INC-99"}).status_code == 404
    assert c.get("/voice/audio", params={"what": "offer", "ref": "O-9"}).status_code == 404
    assert len(fake.tts_calls) == 1


def test_audio_supports_byte_ranges_because_safari_requires_them(rig):
    c, _, _ = rig
    inc = report(c)
    q = {"what": "readback", "ref": inc["id"], "lang": "en"}
    full = c.get("/voice/audio", params=q)
    n = len(full.content)
    assert full.headers["accept-ranges"] == "bytes" and full.status_code == 200
    part = c.get("/voice/audio", params=q, headers={"Range": "bytes=0-1"})
    assert (
        part.status_code == 206
        and part.content == full.content[:2]
        and part.headers["content-range"] == f"bytes 0-1/{n}"
    )
    tail = c.get("/voice/audio", params=q, headers={"Range": "bytes=10-"})
    assert tail.status_code == 206 and tail.content == full.content[10:]
    last = c.get("/voice/audio", params=q, headers={"Range": "bytes=-5"})
    assert last.content == full.content[-5:] and last.status_code == 206
    assert c.get("/voice/audio", params=q, headers={"Range": f"bytes={n + 5}-"}).status_code == 416
    assert c.get("/voice/audio", params=q, headers={"Range": "bytes=oops"}).status_code == 200  # nonsense is ignored


def test_offers_and_notes_can_be_spoken(rig):
    c, fake, _ = rig
    iid = report(c)["id"]
    c.post(f"/incidents/{iid}/confirm", json={"confirmed": True})
    v = c.get(f"/incidents/{iid}/proposal").json()["proposal"]["plan_version"]
    out = c.post(
        f"/incidents/{iid}/approve", json={"approved_by": "head", "shortlist": ["V4"], "proposal_version": v}
    ).json()
    offer = out["incident"]["active_offer"]
    assert c.get("/voice/audio", params={"what": "offer", "ref": offer["id"], "lang": "hi"}).status_code == 200
    assert "हडपसर" in fake.tts_calls[-1].content.decode()
    note = c.get("/notifications", params={"to": "driver:Ravi"}).json()["notifications"][0]
    assert c.get("/voice/audio", params={"what": "note", "ref": str(note["id"]), "lang": "en"}).status_code == 200


def test_when_voice_is_off_or_fails_the_screen_is_told_to_fall_back(tmp_path):
    off = TestClient(create_app(None, start_ticker=False))
    inc = off.post("/incidents/report", json={"driver": "Ravi", "transcript": "broke down near Hadapsar"}).json()[
        "incident"
    ]
    r = off.get("/voice/audio", params={"what": "readback", "ref": inc["id"], "lang": "en"})
    assert r.status_code == 503 and r.json()["code"] == "voice_off"
    assert off.get("/voice/status").json()["enabled"] is False
    assert off.post("/voice/warm").status_code == 503
    broken = TestClient(create_app(None, start_ticker=False, voice=service(Fake(status=429), tmp_path)))
    inc = broken.post("/incidents/report", json={"driver": "Ravi", "transcript": "broke down near Hadapsar"}).json()[
        "incident"
    ]
    r = broken.get("/voice/audio", params={"what": "readback", "ref": inc["id"], "lang": "en"})
    assert r.status_code == 503 and r.json()["code"] == "voice_quota"


def test_a_spoken_report_becomes_an_incident(rig):
    c, fake, app = rig
    r = c.post(
        "/incidents/voice", params={"driver": "Ravi"}, content=AUDIO, headers={"content-type": "audio/webm;codecs=opus"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == "My truck broke down near Hadapsar" and body["detected_language"] == "en"
    inc = body["incident"]
    assert inc["source"] == "voice" and inc["state"] == "REPORTED" and inc["location_id"] == "hadapsar"
    log = c.get("/audit?limit=500").json()["entries"]
    heard = [e for e in log if e["action"] == "voice_transcribed"][-1]["details"]
    assert heard["engine"] == "elevenlabs" and heard["detected"] == "eng" and heard["audio_bytes"] == len(AUDIO)
    rep = [e for e in log if e["action"] == "incident_reported"][-1]["details"]
    assert rep["source"] == "voice" and rep["engine"] == "elevenlabs"
    assert "secret-key" not in str(log)


def test_a_spoken_report_about_an_unknown_place_is_rejected_like_a_typed_one(tmp_path):
    fake = Fake(transcript="mera truck Atlantis ke paas kharab ho gaya", lang="hin")
    c = TestClient(create_app(None, start_ticker=False, voice=service(fake, tmp_path)))
    r = c.post("/incidents/voice", params={"driver": "Ravi"}, content=AUDIO, headers={"content-type": "audio/webm"})
    assert (
        r.status_code == 200 and r.json()["incident"]["state"] == "REJECTED" and r.json()["incident"]["known_locations"]
    )


def test_bad_recordings_are_refused_before_any_credit_is_spent(rig):
    c, fake, _ = rig
    h = {"content-type": "audio/webm"}
    assert (
        c.post("/incidents/voice", params={"driver": "Ravi"}, content=b"tiny", headers=h).json()["code"]
        == "nothing_heard"
    )
    assert c.post("/incidents/voice", params={"driver": "Ravi"}, content=b"x" * 3_100_000, headers=h).status_code == 413
    assert not fake.calls
    fake.transcript = "   "
    assert (
        c.post("/incidents/voice", params={"driver": "Ravi"}, content=AUDIO, headers=h).json()["code"]
        == "nothing_heard"
    )
    assert c.get("/incidents").json()["incidents"] == []  # nothing was created


def test_if_transcription_fails_nothing_is_created_and_the_screen_can_fall_back(tmp_path):
    c = TestClient(create_app(None, start_ticker=False, voice=service(Fake(status=500), tmp_path)))
    r = c.post("/incidents/voice", params={"driver": "Ravi"}, content=AUDIO, headers={"content-type": "audio/webm"})
    assert r.status_code == 503 and r.json()["code"] == "voice_unavailable"
    assert c.get("/incidents").json()["incidents"] == []
    # the browser can then send its own transcript through the ordinary route, marked as such
    ok = c.post(
        "/incidents/report",
        json={"driver": "Ravi", "transcript": "broke down near Hadapsar", "source": "voice", "engine": "browser"},
    )
    assert ok.status_code == 200 and ok.json()["incident"]["source"] == "voice"
    assert [e for e in c.get("/audit?limit=500").json()["entries"] if e["action"] == "incident_reported"][-1][
        "details"
    ]["engine"] == "browser"


def test_voice_generation_is_audited_without_the_audio(rig):
    c, fake, _ = rig
    inc = report(c)
    c.get("/voice/audio", params={"what": "readback", "ref": inc["id"], "lang": "en"})
    gen = [e for e in c.get("/audit?limit=500").json()["entries"] if e["action"] == "voice_generated"]
    assert (
        gen
        and gen[-1]["details"]["chars"] > 0
        and "audio" not in str(gen[-1]["details"]).lower().replace("audio_bytes", "")
    )


# --- the demo is ready before it starts ---
def test_the_demo_lines_are_exactly_what_the_real_flow_says(tmp_path):
    """If the warm-up and the real flow differ by one word, the demo pays for it live. Run the story and compare."""
    fake = Fake()
    v = service(fake, tmp_path)
    summary = warm(v)
    assert summary["problems"] == [] and summary["generated"] == len(demo_lines()) == len(fake.tts_calls)
    assert summary["generated"] >= 7 and summary["characters"] < 1500  # about a thousand characters in all

    # now play the real story through the API with the same cache: nothing new is generated
    app = create_app(None, start_ticker=False, voice=v)
    c = TestClient(app)
    paid = len(fake.tts_calls)
    inc = c.post(
        "/incidents/report",
        json={"driver": "Ravi", "transcript": "My truck broke down near Hadapsar and I can't make the 3 PM delivery."},
    ).json()["incident"]
    c.get("/voice/audio", params={"what": "readback", "ref": inc["id"], "lang": inc["language"]})
    c.post(f"/incidents/{inc['id']}/confirm", json={"confirmed": True})
    p = c.get(f"/incidents/{inc['id']}/proposal").json()["proposal"]
    shortlist = [x["vehicle_id"] for x in p["candidates"] if x["feasible"]][:3]
    c.post(
        f"/incidents/{inc['id']}/approve",
        json={"approved_by": "head", "shortlist": shortlist, "proposal_version": p["plan_version"]},
    )
    for _ in shortlist:
        off = c.get(f"/incidents/{inc['id']}").json()["incident"]["active_offer"]
        c.get("/voice/audio", params={"what": "offer", "ref": off["id"], "lang": off["language"]})
        c.post(f"/offers/{off['id']}/respond", json={"response": "decline"})
    for n in c.get("/notifications", params={"to": "driver:Ravi"}).json()["notifications"]:
        c.get("/voice/audio", params={"what": "note", "ref": str(n["id"]), "lang": inc["language"]})
    assert len(fake.tts_calls) == paid, "the story said something the warm-up did not prepare"


def test_warm_is_repeatable_for_free(tmp_path):
    fake = Fake()
    v = service(fake, tmp_path)
    warm(v)
    n = len(fake.tts_calls)
    again = warm(v)
    assert again["generated"] == 0 and again["already_cached"] == len(demo_lines()) and len(fake.tts_calls) == n
    assert len(demo_lines(everyone=True)) > len(demo_lines())  # every language on request


def test_warm_reports_what_it_could_not_do(tmp_path):
    out = warm(service(Fake(status=500), tmp_path))
    assert out["generated"] == 0 and out["problems"]


# --- the real thing, only when asked ---
@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_VOICE") or not os.environ.get("ELEVENLABS_API_KEY"), reason="live voice test"
)
@pytest.mark.parametrize(
    ("lang", "text"), [("en", "Breakdown at Hadapsar. Is that correct?"), ("mr", "हडपसर येथे गाडी बिघडली. बरोबर आहे का?")]
)
def test_live_speech_survives_a_round_trip(lang, text, tmp_path):
    v = from_env(dict(os.environ), tmp_path)
    heard = v.transcribe(v.speak(text, lang), "audio/mpeg")
    assert heard.text.replace("।", ".") == text.replace("।", ".")
