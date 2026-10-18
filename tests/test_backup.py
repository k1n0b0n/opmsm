"""Backup orchestration, with edl replaced by a fake that writes partition dumps."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from opmsm import backup
from opmsm.devices import KEBAB


@pytest.fixture
def loader(tmp_path: Path) -> Path:
    path = tmp_path / "prog_firehose_ddr.elf"
    path.write_bytes(b"loader")
    return path


@pytest.fixture
def fake_edl(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(command: list[str], check: bool) -> subprocess.CompletedProcess:
        calls.append(command)
        out = Path(command[2])
        (out / "xbl_a.bin").write_bytes(b"xbl")
        (out / "rawprogram1.xml").write_text("<data />")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(backup.shutil, "which", lambda _: "/usr/bin/edl")
    monkeypatch.setattr(backup.subprocess, "run", run)
    return calls


def test_reads_everything_but_userdata_with_the_device_auth(loader: Path, fake_edl: list, tmp_path: Path) -> None:
    backup.run(KEBAB, loader, tmp_path / "out")

    [command] = fake_edl
    assert command[1] == "rl"
    assert "--skip=userdata" in command
    assert "--devicemodel=19805" in command
    assert "--memory=ufs" in command


def test_manifest_lets_verify_catch_a_changed_file(loader: Path, fake_edl: list, tmp_path: Path) -> None:
    out = tmp_path / "out"
    manifest = backup.run(KEBAB, loader, out)

    assert set(manifest["files"]) == {"xbl_a.bin", "rawprogram1.xml"}
    assert backup.verify(out) == []
    (out / "xbl_a.bin").write_bytes(b"corrupted")
    assert backup.verify(out) == ["xbl_a.bin"]


def test_refuses_to_write_into_a_non_empty_directory(loader: Path, fake_edl: list, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "old.bin").write_bytes(b"old")

    with pytest.raises(backup.BackupError, match="not empty"):
        backup.run(KEBAB, loader, out)
    assert fake_edl == []
