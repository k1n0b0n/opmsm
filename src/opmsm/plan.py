"""Turn an extracted MSM package into per-LUN rawprogram files for one RAM type.

Every check here runs before anything touches the phone. Any doubt aborts the plan:
a multi-image partition the device profile does not know, a DDR-dependent partition
without exactly one image for the requested RAM type, a missing image or a checksum mismatch.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from opmsm.devices import Ddr, Device
from opmsm.settings import Image, Partition, Settings


class PlanError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    partition: Partition
    image: Image


@dataclass(frozen=True)
class Plan:
    loader: Path
    entries: list[Entry]
    patches: dict[int, list[dict[str, str]]]

    @property
    def luns(self) -> list[int]:
        return sorted({entry.partition.lun for entry in self.entries})


SECTOR = 0x1000


def package_sha256(path: Path) -> str:
    """SHA-256 as settings.xml records it: over the image zero-padded to a 4 KiB sector."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    if size % SECTOR:
        digest.update(b"\x00" * (SECTOR - size % SECTOR))
    return digest.hexdigest()


def _base_label(label: str) -> str:
    return re.sub(r"_[ab]$", "", label)


def select_loader(settings: Settings, device: Device, ddr: Ddr) -> str:
    wanted = [
        loader.path for loader in settings.loaders
        if not loader.lite and Path(loader.path).stem == device.loaders[ddr]
    ]
    if len(wanted) != 1:
        found = [loader.path for loader in settings.loaders]
        raise PlanError(f"need exactly one {ddr.value} Firehose loader, package has {found}")
    return wanted[0]


def _ddr_image(partition: Partition, device: Device, ddr: Ddr) -> Image:
    stems = device.ddr_images[_base_label(partition.label)]
    ids = device.ddr_image_ids
    unknown = [i.filename for i in partition.images if (i.stem, i.id) not in {(stems[d], ids[d]) for d in Ddr}]
    if unknown:
        raise PlanError(f"unexpected image(s) for DDR-dependent partition {partition.label!r}: {unknown}")
    wanted = [i for i in partition.images if i.stem == stems[ddr] and i.id == ids[ddr]]
    if len(wanted) != 1:
        found = [i.filename for i in partition.images]
        raise PlanError(f"need exactly one {ddr.value} image for {partition.label!r}, package has {found}")
    return wanted[0]


def select_images(settings: Settings, device: Device, ddr: Ddr) -> list[Entry]:
    entries = []
    seen_ddr_labels = set()
    for partition in settings.partitions:
        if not partition.images:
            continue
        if _base_label(partition.label) in device.ddr_images:
            seen_ddr_labels.add(_base_label(partition.label))
            entries.append(Entry(partition, _ddr_image(partition, device, ddr)))
        elif partition.multi_image or len(partition.images) > 1:
            found = [i.filename for i in partition.images]
            raise PlanError(f"multi-image partition {partition.label!r} unknown to the {device.codename} profile: {found}")
        else:
            entries.append(Entry(partition, partition.images[0]))
    missing = sorted(device.ddr_images.keys() - seen_ddr_labels)
    if missing:
        raise PlanError(f"package has no image for DDR-dependent partition(s) {missing}")
    return entries


def build(settings: Settings, device: Device, ddr: Ddr, extract_dir: Path) -> Plan:
    loader = extract_dir / select_loader(settings, device, ddr)
    if not loader.exists():
        raise PlanError(f"missing loader {loader}")

    entries = select_images(settings, device, ddr)
    for entry in entries:
        path = extract_dir / entry.image.filename
        if not path.exists():
            raise PlanError(f"missing image {path}")
        # opscrypto only checks non-sparse images; sparse ones are hashed unsparsed by MSM.
        if not entry.image.sparse and package_sha256(path) != entry.image.sha256.lower():
            raise PlanError(f"checksum mismatch for {path}")
    return Plan(loader=loader, entries=entries, patches=settings.patches)


def _write(root: ET.Element, path: Path) -> Path:
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def write_rawprograms(plan: Plan, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for lun in plan.luns:
        root = ET.Element("data")
        for entry in (e for e in plan.entries if e.partition.lun == lun):
            attributes = {k: v for k, v in entry.partition.attributes.items() if k != "multiImage"}
            attributes |= {"filename": entry.image.filename, "sparse": str(entry.image.sparse).lower()}
            ET.SubElement(root, "program", attributes)
        written.append(_write(root, out_dir / f"rawprogram{lun}.xml"))
        if plan.patches.get(lun):
            patches = ET.Element("patches")
            for patch in plan.patches[lun]:
                ET.SubElement(patches, "patch", patch)
            written.append(_write(patches, out_dir / f"patch{lun}.xml"))
    return written
