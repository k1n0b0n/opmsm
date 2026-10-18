"""Read-only full backup of a phone over EDL, through bkerler/edl.

A backup holds every partition of every UFS LUN except userdata, plus the GPTs and the
rawprogram files edl generates, so the exact state (firmware, super layout) can be written
back later. It also holds this phone's IMEI and calibration data (modemst, fsg, persist):
it belongs to one phone only and must never be shared.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from opmsm.devices import Device

SKIPPED = ("userdata",)
MANIFEST = "opmsm-backup.json"


class BackupError(Exception):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def edl_command(device: Device, loader: Path, out_dir: Path) -> list[str]:
    edl = shutil.which("edl")
    if edl is None:
        raise BackupError("edl not found: run opmsm through `uv run`")
    return [
        edl, "rl", str(out_dir),
        "--memory=ufs",
        f"--skip={','.join(SKIPPED)}",
        "--genxml",
        f"--loader={loader}",
        f"--devicemodel={device.project_id}",
    ]


def write_manifest(out_dir: Path, device: Device, loader: Path) -> dict:
    files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.name != MANIFEST)
    if not any(p.suffix == ".bin" for p in files):
        raise BackupError(f"edl wrote no partition image in {out_dir}")
    manifest = {
        "device": device.codename,
        "project_id": device.project_id,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "skipped": list(SKIPPED),
        "loader": {"name": loader.name, "sha256": _sha256(loader)},
        "edlclient": version("edlclient"),
        "files": {str(p.relative_to(out_dir)): _sha256(p) for p in files},
    }
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def run(device: Device, loader: Path, out_dir: Path) -> dict:
    if not loader.is_file():
        raise BackupError(f"missing Firehose loader {loader}")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise BackupError(f"{out_dir} is not empty, refusing to mix two backups")
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(edl_command(device, loader, out_dir), check=True)
    return write_manifest(out_dir, device, loader)


def verify(out_dir: Path) -> list[str]:
    """Return the files whose content no longer matches the manifest."""
    manifest = json.loads((out_dir / MANIFEST).read_text())
    return [
        name for name, digest in manifest["files"].items()
        if not (out_dir / name).is_file() or _sha256(out_dir / name) != digest
    ]
