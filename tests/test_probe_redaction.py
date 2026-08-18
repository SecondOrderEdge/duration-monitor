"""The probe must never write a credential into its evidence files.

`scripts/probe_sources.py` exists to have its output committed, and a failed
`requests` call stringifies to the full request URL — `api_key` included. GitHub
Actions masks secrets in job logs but not in files a job commits, so a leak here
would land in git history in plaintext.

The likeliest trigger is exactly what the probe is for: an unverified series ID
that 404s.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# scripts/ is not a package, so load the module by path.
_spec = importlib.util.spec_from_file_location(
    "probe_sources", REPO_ROOT / "scripts" / "probe_sources.py"
)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

FAKE_KEY = "abcdef0123456789abcdef0123456789"   # not real; the shape FRED requires


@pytest.fixture(autouse=True)
def _clean_registry():
    """Keep registered secrets from leaking between tests."""
    before = set(probe._REDACT_TOKENS)
    yield
    probe._REDACT_TOKENS.clear()
    probe._REDACT_TOKENS.update(before)


def test_registered_secret_is_scrubbed():
    probe.register_secret(FAKE_KEY)
    text = (
        "HTTPError: 400 Client Error: Bad Request for url: "
        f"https://api.stlouisfed.org/fred/series?series_id=NOPE&api_key={FAKE_KEY}"
        "&file_type=json"
    )
    out = probe._redact(text)

    assert FAKE_KEY not in out
    assert "***REDACTED***" in out
    assert "series_id=NOPE" in out          # the diagnostic value is preserved


def test_api_key_parameter_is_scrubbed_even_when_unregistered():
    """Defence in depth: a key arriving by a path we did not anticipate."""
    out = probe._redact("...?series_id=X&api_key=someothersecret&file_type=json")

    assert "someothersecret" not in out
    assert "series_id=X" in out
    assert "file_type=json" in out          # redaction stops at the parameter


def test_register_secret_ignores_empty_values():
    probe.register_secret(None)
    probe.register_secret("")
    # An empty token would otherwise match everywhere and destroy the text.
    assert probe._redact("harmless text") == "harmless text"


def test_serialised_report_is_scrubbed_as_a_whole():
    """The final safety net, applied to the JSON on its way to disk."""
    probe.register_secret(FAKE_KEY)
    report = {"fred": {"series": {"X": {"error": f"boom api_key={FAKE_KEY}"}}}}

    written = probe._redact(json.dumps(report, indent=2, default=str))

    assert FAKE_KEY not in written
    assert json.loads(written)["fred"]["series"]["X"]["error"].startswith("boom")


def test_no_key_means_fred_is_skipped_not_probed_with_none():
    result = probe.probe_fred({"base_url": "https://example.invalid/"}, None, 5)
    assert result["status"] == "skipped"
