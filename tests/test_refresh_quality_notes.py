"""Every quality event refresh.py can emit must use a type the log accepts.

The bug this guards against cost a full pipeline run. A builder appended a note
with an invented `event_type`, every source fetched and validated correctly, and
the script then died in the last few lines while folding notes into the log —
four minutes in, with all the work done and the exit code set to failure.

The quality log is right to keep a closed vocabulary. The gap was that nothing
checked the callers against it until runtime, so the check is done statically
here: it reads the literal event_type strings out of the script rather than
running it.
"""

from __future__ import annotations

import ast
import pathlib

from src.validation.quality import EVENT_TYPES

REFRESH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "refresh.py"


def _event_types_in(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and key.value == "event_type"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                found.add(value.value)
    return found


def test_refresh_only_emits_known_event_types():
    used = _event_types_in(REFRESH)
    assert used, "found no literal event_type in refresh.py; the check would pass vacuously"
    unknown = sorted(used - set(EVENT_TYPES))
    assert not unknown, (
        f"refresh.py emits quality events typed {unknown}, which the log will "
        f"reject at the end of a full run. Known types: {sorted(EVENT_TYPES)}"
    )
