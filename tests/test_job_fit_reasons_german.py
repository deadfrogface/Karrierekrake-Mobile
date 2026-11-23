"""Every reason the matcher writes has German wording in the job list (no English in the German UI)."""
import ast
import re
from pathlib import Path

from desktop.viewmodels.job_fit import humanize_reason

ROOT = Path(__file__).resolve().parents[1]


def _reason_templates() -> list[str]:
    """String and f-string reason texts in core/intent_filter.py, with each placeholder filled by a sample."""
    tree = ast.parse((ROOT / "core" / "intent_filter.py").read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in {"detail", "detail_hit", "detail_ok"}:
            values = [node.value]
        elif isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "detail" for t in node.targets):
            values = [node.value]
        else:
            continue
        while values:
            value = values.pop()
            if isinstance(value, ast.IfExp):
                values += [value.body, value.orelse]
            elif isinstance(value, ast.Constant) and isinstance(value.value, str):
                out.append(value.value)
            elif isinstance(value, ast.JoinedStr):
                out.append("".join(p.value if isinstance(p, ast.Constant) else "20" for p in value.values))
    return out


def test_every_matcher_reason_is_translated():
    templates = _reason_templates()
    assert len(templates) >= 30
    untranslated = [t for t in templates if humanize_reason(t) == t]
    assert untranslated == []


def test_target_role_reads_german():
    assert humanize_reason("✓ target role: Office Manager") == "Wunschrolle: Office Manager"
    assert not re.search(r"target role", humanize_reason("target role (assistenz): Teamassistenz"))
