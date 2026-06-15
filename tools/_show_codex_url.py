# -*- coding: utf-8 -*-
"""Just print a sample Codex authorize URL (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.codex_oauth import _generate_pkce, _generate_state, _build_authorize_url

verifier, challenge = _generate_pkce()
state = _generate_state()

print("--- authorize URL (prompt=login) ---")
print(_build_authorize_url(state, challenge, "login"))
print()
print("--- authorize URL (prompt=none) ---")
print(_build_authorize_url(state, challenge, "none"))
print()
print("code_verifier (head):", verifier[:24] + "...")
print("code_challenge:      ", challenge)
print("state:               ", state)