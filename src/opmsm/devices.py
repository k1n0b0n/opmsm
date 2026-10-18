"""Device profiles: what the tool knows for sure about each supported phone."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Ddr(str, Enum):
    DDR4 = "ddr4"
    DDR5 = "ddr5"


@dataclass(frozen=True)
class Device:
    codename: str
    name: str
    # OnePlus project id used by the EDL authentication (edlclient oneplus module).
    project_id: str
    models: tuple[str, ...]
    # Partitions whose image depends on the RAM type: label without slot -> image stem per DDR.
    ddr_images: dict[str, dict[Ddr, str]]
    # ID attribute of those images in settings.xml, checked on top of the file name.
    ddr_image_ids: dict[Ddr, str]
    # Firehose loader stem per DDR (SAHARA DPIndex 1 and 2).
    loaders: dict[Ddr, str]


# Sources: LineageOS wiki firmware guide for kebab (xbl/xbl_config for DDR4,
# xbl_lp5/xbl_config_lp5 for DDR5), edlclient's oneplus module (project 19805) and the
# settings.xml of kebab_15_E.12_201110 (image IDs 4 and 65540, SAHARA comment
# "1: Normal DDR DP, 2: LPDDR5 DP").
KEBAB = Device(
    codename="kebab",
    name="OnePlus 8T",
    project_id="19805",
    models=("KB2000", "KB2001", "KB2003", "KB2005"),
    ddr_images={
        "xbl": {Ddr.DDR4: "xbl", Ddr.DDR5: "xbl_lp5"},
        "xbl_config": {Ddr.DDR4: "xbl_config", Ddr.DDR5: "xbl_config_lp5"},
    },
    ddr_image_ids={Ddr.DDR4: "4", Ddr.DDR5: "65540"},
    loaders={Ddr.DDR4: "prog_firehose_ddr", Ddr.DDR5: "prog_firehose_ddr_lp5"},
)

DEVICES = {device.codename: device for device in (KEBAB,)}

# Close relatives that must not fall back on a sibling profile. Source: edlclient's oneplus
# module gives the T-Mobile 8T its own project id (20809); it also has its own MSM package (KB09CB).
REFUSED = {
    "kebabt": "T-Mobile OnePlus 8T (KB2007) is not supported yet: it has its own EDL project id "
              "(20809) and MSM package (KB09CB), never use the kebab profile for it",
}


def get_device(codename: str) -> Device:
    if codename in REFUSED:
        raise ValueError(REFUSED[codename])
    try:
        return DEVICES[codename]
    except KeyError:
        supported = ", ".join(sorted(DEVICES))
        raise ValueError(f"unknown device {codename!r} (supported: {supported})") from None
