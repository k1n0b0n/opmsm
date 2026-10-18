"""Plan checks on a synthetic package laid out like the settings.xml of kebab_15_E.12_201110."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from opmsm import plan, settings
from opmsm.devices import KEBAB, Ddr, get_device

SAHARA = (
    '<SAHARA>'
    '<File Id="13" DPIndex="0" isLite="true" Path="prog_firehose_lite.elf" />'
    '<File Id="13" DPIndex="1" isLite="false" Path="prog_firehose_ddr.elf" />'
    '<File Id="13" DPIndex="2" isLite="false" Path="prog_firehose_ddr_lp5.elf" />'
    '</SAHARA>'
)


def _image(name: str, data: bytes, directory: Path, image_id: str = "0") -> str:
    (directory / name).write_bytes(data)
    sha = plan.package_sha256(directory / name)
    return f'<Image ID="{image_id}" filename="{name}" sparse="false" Sha256="{sha}" FileOffsetInSrc="0" />'


def _program(label: str, images: list[str], multi: bool = False) -> str:
    return (
        f'<program label="{label}" physical_partition_number="1" start_sector="6" '
        f'multiImage="{str(multi).lower()}">{"".join(images)}</program>'
    )


def make_package(directory: Path, programs: list[str]) -> Path:
    for loader in ("prog_firehose_lite.elf", "prog_firehose_ddr.elf", "prog_firehose_ddr_lp5.elf"):
        (directory / loader).write_bytes(b"loader")
    patch = '<Patch1><patch filename="DISK" start_sector="4" value="0" /></Patch1>'
    xml = f"<Setting>{SAHARA}<Program1>{''.join(programs)}</Program1>{patch}</Setting>"
    (directory / "settings.xml").write_text(xml)
    return directory


def _xbl_pair(directory: Path) -> list[str]:
    return [
        _program("xbl_a", [_image("xbl_lp5.elf", b"ddr5", directory, "65540"),
                           _image("xbl.elf", b"ddr4", directory, "4")], multi=True),
        _program("xbl_config_a", [_image("xbl_config_lp5.elf", b"cfg5", directory, "65540"),
                                  _image("xbl_config.elf", b"cfg4", directory, "4")], multi=True),
    ]


@pytest.fixture
def package(tmp_path: Path) -> Path:
    return make_package(tmp_path, [
        *_xbl_pair(tmp_path),
        _program("abl_a", [_image("abl.elf", b"abl", tmp_path)]),
        _program("xbl_b", ['<Image ID="0" filename="" Sha256="0" />']),
    ])


def _build(package: Path, ddr: Ddr) -> plan.Plan:
    return plan.build(settings.parse(package / "settings.xml"), KEBAB, ddr, package)


@pytest.mark.parametrize(("ddr", "loader", "expected"), [
    (Ddr.DDR4, "prog_firehose_ddr.elf", {"xbl.elf", "xbl_config.elf"}),
    (Ddr.DDR5, "prog_firehose_ddr_lp5.elf", {"xbl_lp5.elf", "xbl_config_lp5.elf"}),
])
def test_picks_the_loader_and_xbl_pair_for_the_requested_ram(
    package: Path, ddr: Ddr, loader: str, expected: set[str]
) -> None:
    built = _build(package, ddr)

    assert built.loader.name == loader
    assert {e.image.filename for e in built.entries} == expected | {"abl.elf"}


def test_rawprogram_has_one_image_per_partition_and_keeps_patches(package: Path, tmp_path: Path) -> None:
    written = plan.write_rawprograms(_build(package, Ddr.DDR4), tmp_path / "out")

    assert [p.name for p in written] == ["rawprogram1.xml", "patch1.xml"]
    programs = ET.parse(written[0]).getroot().findall("program")
    assert {p.attrib["label"]: p.attrib["filename"] for p in programs} == {
        "xbl_a": "xbl.elf", "xbl_config_a": "xbl_config.elf", "abl_a": "abl.elf",
    }
    assert all("multiImage" not in p.attrib for p in programs)


def test_checksum_covers_the_zero_padding_to_a_sector(tmp_path: Path) -> None:
    path = tmp_path / "odd.bin"
    path.write_bytes(b"x" * 5000)

    assert plan.package_sha256(path) == hashlib.sha256(b"x" * 5000 + b"\x00" * 3192).hexdigest()


def test_refuses_an_image_whose_id_does_not_match_its_name(tmp_path: Path) -> None:
    make_package(tmp_path, [
        _program("xbl_a", [_image("xbl_lp5.elf", b"ddr5", tmp_path, "4"),
                           _image("xbl.elf", b"ddr4", tmp_path, "4")], multi=True),
        _xbl_pair(tmp_path)[1],
    ])

    with pytest.raises(plan.PlanError, match="unexpected image"):
        _build(tmp_path, Ddr.DDR4)


def test_refuses_a_missing_ddr_variant(tmp_path: Path) -> None:
    make_package(tmp_path, [
        _program("xbl_a", [_image("xbl.elf", b"ddr4", tmp_path, "4")], multi=True),
        _xbl_pair(tmp_path)[1],
    ])

    with pytest.raises(plan.PlanError, match="ddr5 image for 'xbl_a'"):
        _build(tmp_path, Ddr.DDR5)


def test_refuses_a_package_without_the_ddr_partitions(tmp_path: Path) -> None:
    make_package(tmp_path, [_program("abl_a", [_image("abl.elf", b"abl", tmp_path)])])

    with pytest.raises(plan.PlanError, match="no image for DDR-dependent"):
        _build(tmp_path, Ddr.DDR4)


def test_refuses_an_unknown_multi_image_partition(package: Path) -> None:
    make_package(package, [
        *_xbl_pair(package),
        _program("modem_a", [_image("modem.bin", b"m1", package, "4"),
                             _image("modem_lp5.bin", b"m2", package, "65540")], multi=True),
    ])

    with pytest.raises(plan.PlanError, match="multi-image partition 'modem_a'"):
        _build(package, Ddr.DDR4)


def test_refuses_a_corrupted_image(package: Path) -> None:
    (package / "abl.elf").write_bytes(b"tampered")

    with pytest.raises(plan.PlanError, match="checksum mismatch"):
        _build(package, Ddr.DDR4)


def test_refuses_the_t_mobile_variant() -> None:
    with pytest.raises(ValueError, match="T-Mobile"):
        get_device("kebabt")
