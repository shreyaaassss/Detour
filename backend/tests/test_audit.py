import json

from detour.audit import GENESIS, AuditLog


def make(path=None):
    log = AuditLog(path)
    log.append("system", "a", {"x": 1})
    log.append("dispatcher", "b", {"y": [1, 2]}, sim_time=845)
    log.append("head", "c")
    return log


def test_chain_links_and_verifies():
    log = make()
    assert log.entries[0].prev_hash == GENESIS
    assert all(log.entries[i].prev_hash == log.entries[i - 1].hash for i in range(1, 3))
    assert log.verify()["valid"]


def test_editing_an_entry_is_detected():
    log = make()
    log.entries[1].details["y"] = [9]
    v = log.verify()
    assert not v["valid"] and v["broken_at"] == 2 and "modified" in v["reason"]


def test_deleting_or_reordering_is_detected():
    log = make()
    del log.entries[1]
    assert not log.verify()["valid"]
    log = make()
    log.entries[0], log.entries[1] = log.entries[1], log.entries[0]
    assert not log.verify()["valid"]


def test_rewriting_a_hash_breaks_the_next_link():
    log = make()
    log.entries[0].hash = "f" * 64
    assert log.verify()["broken_at"] in (1, 2)


def test_persists_and_continues_across_restarts(tmp_path):
    p = tmp_path / "audit.jsonl"
    make(p)
    again = AuditLog(p)
    assert len(again.entries) == 3 and again.verify()["valid"]
    again.append("system", "d")
    assert len(AuditLog(p).entries) == 4 and AuditLog(p).verify()["valid"]


def test_tampered_file_is_archived_and_never_extended(tmp_path):
    p = tmp_path / "audit.jsonl"
    make(p)
    lines = p.read_text().splitlines()
    e = json.loads(lines[1])
    e["details"]["y"] = [999]
    lines[1] = json.dumps(e)
    p.write_text("\n".join(lines) + "\n")
    fresh = AuditLog(p)
    assert fresh.entries == [] and fresh.archived is not None and fresh.archived.exists()
    assert not p.exists()


def test_append_callback_fires():
    seen = []
    log = AuditLog(None, on_append=seen.append)
    log.append("system", "x")
    assert [e.action for e in seen] == ["x"]


def test_tail_and_after():
    log = make()
    assert [e.id for e in log.tail(limit=2)] == [2, 3]
    assert [e.id for e in log.tail(after=1)] == [2, 3]
