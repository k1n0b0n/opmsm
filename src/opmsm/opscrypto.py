"""Decrypt an MSM .ops package with bkerler/oppo_decrypt.

oppo_decrypt has no license, so its code is not vendored here: the script is downloaded
at a pinned commit, checked against a known SHA-256 and run as a separate process.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

COMMIT = "3456e850fb408f4dfab43e9788970c9be2caa743"
URL = f"https://raw.githubusercontent.com/bkerler/oppo_decrypt/{COMMIT}/opscrypto.py"
SHA256 = "d98a0b7ac5b4c8f99affdf4787a76d5a9576d4bf7b02d0f3d34cab1890130d1d"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "opmsm"


def fetch() -> Path:
    script = cache_dir() / f"opscrypto-{COMMIT[:12]}.py"
    if not script.exists():
        script.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL, timeout=60) as response:
            data = response.read()
        script.write_bytes(data)
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    if digest != SHA256:
        script.unlink()
        raise RuntimeError(f"opscrypto.py checksum mismatch ({digest}), refusing to run it")
    return script


def decrypt(ops_file: Path, extract_dir: Path) -> None:
    script = fetch()
    extract_dir.mkdir(parents=True, exist_ok=True)
    # -I keeps the interpreter from importing modules sitting next to the package files.
    subprocess.run(
        [sys.executable, "-I", str(script), "decrypt", str(ops_file), f"--extractdir={extract_dir}"],
        check=True,
    )
    if not (extract_dir / "settings.xml").exists():
        raise RuntimeError(f"decryption produced no settings.xml in {extract_dir}")
