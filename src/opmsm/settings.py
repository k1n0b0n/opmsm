"""Read the settings.xml that opscrypto extracts from an MSM .ops package.

Layout, as seen in kebab_15_E.12_201110 (OnePlus 8T EU):

- SAHARA lists the Firehose loaders as <File DPIndex=... isLite=... Path=...>;
- UFS_PROVISION lists <File Path=...>;
- Program<N> holds the partitions of UFS LUN N, one <program> each, with its images as
  <Image ID=... filename=... Sha256=... sparse=...> children. A partition with
  multiImage="true" carries one image per RAM type and the tool must pick exactly one;
- Patch<N> holds the GPT <patch> entries of LUN N.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Loader:
    dp_index: int
    lite: bool
    path: str


@dataclass(frozen=True)
class Image:
    id: str
    filename: str
    sha256: str
    sparse: bool

    @property
    def stem(self) -> str:
        return Path(self.filename).stem


@dataclass(frozen=True)
class Partition:
    lun: int
    label: str
    # Attributes of the <program> element, the ones a rawprogram file needs.
    attributes: dict[str, str]
    images: tuple[Image, ...]

    @property
    def multi_image(self) -> bool:
        return self.attributes.get("multiImage") == "true"


@dataclass
class Settings:
    loaders: list[Loader] = field(default_factory=list)
    provisioning: list[str] = field(default_factory=list)
    partitions: list[Partition] = field(default_factory=list)
    patches: dict[int, list[dict[str, str]]] = field(default_factory=dict)
    other_sections: list[str] = field(default_factory=list)


def _images(program: ET.Element) -> tuple[Image, ...]:
    return tuple(
        Image(
            id=image.attrib.get("ID", ""),
            filename=image.attrib["filename"],
            sha256=image.attrib.get("Sha256", ""),
            sparse=image.attrib.get("sparse", "false") == "true",
        )
        for image in program.iter("Image")
        if image.attrib.get("filename", "") != ""
    )


def parse(path: Path) -> Settings:
    root = ET.parse(path).getroot()
    settings = Settings()
    for section in root:
        if section.tag == "SAHARA":
            settings.loaders += [
                Loader(int(f.attrib["DPIndex"]), f.attrib.get("isLite") == "true", f.attrib["Path"])
                for f in section.iter("File")
            ]
        elif section.tag == "UFS_PROVISION":
            settings.provisioning += [f.attrib["Path"] for f in section.iter("File")]
        elif match := re.fullmatch(r"Program(\d+)", section.tag):
            lun = int(match.group(1))
            settings.partitions += [
                Partition(lun, program.attrib.get("label", ""), dict(program.attrib), _images(program))
                for program in section.iter("program")
            ]
        elif match := re.fullmatch(r"Patch(\d+)", section.tag):
            settings.patches[int(match.group(1))] = [dict(p.attrib) for p in section.iter("patch")]
        else:
            settings.other_sections.append(section.tag)
    return settings
