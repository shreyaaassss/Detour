import os

from detour.api import create_app, default_audit_path
from detour.rescue.service import RescueConfig


def _config() -> RescueConfig:
    """Timers from the PRD. Override with DETOUR_<NAME> in seconds to rehearse faster; the push timeout is
    60 s unless you say otherwise."""
    cfg = RescueConfig()
    for name in ("push_timeout", "driver_confirm", "head_response", "ring_timeout", "conversation_limit"):
        v = os.environ.get(f"DETOUR_{name.upper()}")
        if v:
            setattr(cfg, name, float(v))
    return cfg


app = create_app(default_audit_path(), rescue_config=_config())
