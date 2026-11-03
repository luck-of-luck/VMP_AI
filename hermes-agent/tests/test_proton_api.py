"""PROTON v3 backend — buffer-arquivo, upload, skills, health (stdlib+pytest, sem rede)."""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hermes_cli import proton_api as proton


@pytest.fixture
def home_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    # proton_api resolve via get_hermes_home() que lê HERMES_HOME
    return tmp_path


def test_save_buffer_simple(home_tmp):
    res = proton.save_buffer("olá proton", key="prompt")
    assert res["status"] == "ok"
    assert (home_tmp / "crowork_buffer" / "prompt.md").read_text(
        encoding="utf-8"
    ) == "olá proton"
    assert res["chars"] == len("olá proton")


def test_save_buffer_chunks(home_tmp):
    big = "A" * 120000  # cola gigante
    ch = 50000
    total = (len(big) + ch - 1) // ch
    last: dict = {"status": "pending"}
    for i in range(total):
        last = proton.save_buffer(
            big[i * ch : (i + 1) * ch], chunk=i, total=total, key="prompt"
        )
    assert last.get("status") == "ok"
    assert (home_tmp / "crowork_buffer" / "prompt.md").read_text(
        encoding="utf-8"
    ) == big


def test_save_upload_image(home_tmp):
    res = proton.save_upload("foto.png", b"\x89PNG" + b"0" * 100, "image/png")
    assert res["status"] == "ok"
    assert res["kind"] == "image"
    assert res["md_link"].startswith("![foto.png](hermes-images://")
    assert Path(res["path"]).exists()


def test_save_upload_doc(home_tmp):
    res = proton.save_upload("dados.csv", b"a,b\n1,2\n", "text/csv")
    assert res["kind"] == "file"
    assert "hermes-file://" in res["md_link"]


def test_apply_skills(home_tmp):
    res = proton.apply_skills("gemini-3-flash-preview", ["vortex-hermes"])
    assert res["status"] == "ok"
    saved = json.loads(
        (home_tmp / "crowork_buffer" / "skills-applied.json").read_text(
            encoding="utf-8"
        )
    )
    assert saved["model"] == "gemini-3-flash-preview"
    assert "vortex-hermes" in saved["skills"]


def test_health_offline_ok(home_tmp, monkeypatch):
    # sem gateway e sem ollama: health responde offline_ok=True, nunca explode
    import urllib.request as _u

    def _boom(*a, **k):
        raise ConnectionRefusedError("sem rede no teste")

    monkeypatch.setattr(_u, "urlopen", _boom)
    h = proton.health()
    assert h["status"] == "ok"
    assert h["offline_ok"] is True
    assert h["ollama"] is False
