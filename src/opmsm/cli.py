"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from opmsm import backup, opscrypto, plan, settings
from opmsm.devices import DEVICES, Ddr, get_device


def cmd_decrypt(args: argparse.Namespace) -> None:
    opscrypto.decrypt(args.ops, args.out)
    print(f"Extracted to {args.out}")


def cmd_inspect(args: argparse.Namespace) -> None:
    parsed = settings.parse(args.extract_dir / "settings.xml")
    for loader in parsed.loaders:
        print(f"Firehose loader {loader.dp_index}: {loader.path}{' (lite)' if loader.lite else ''}")
    print(f"UFS provisioning: {parsed.provisioning}")
    for lun in sorted({p.lun for p in parsed.partitions}):
        partitions = [p for p in parsed.partitions if p.lun == lun]
        with_image = sum(1 for p in partitions if p.images)
        print(f"LUN {lun}: {len(partitions)} partitions, {with_image} with an image, "
              f"{len(parsed.patches.get(lun, []))} GPT patches")
    multi = [p for p in parsed.partitions if p.multi_image or len(p.images) > 1]
    print(f"Multi-image partitions: {'none' if not multi else ''}")
    for partition in multi:
        images = ", ".join(f"{i.filename} (ID {i.id})" for i in partition.images)
        print(f"  {partition.label} (LUN {partition.lun}): {images}")
    print(f"Other sections: {', '.join(parsed.other_sections) or 'none'}")


def cmd_plan(args: argparse.Namespace) -> None:
    device = get_device(args.device)
    parsed = settings.parse(args.extract_dir / "settings.xml")
    built = plan.build(parsed, device, Ddr(args.ddr), args.extract_dir)
    written = plan.write_rawprograms(built, args.out)
    print(f"{device.name} ({device.codename}), {args.ddr.upper()}")
    print(f"Loader: {built.loader}")
    for entry in built.entries:
        if entry.partition.multi_image:
            print(f"DDR image: {entry.partition.label} <- {entry.image.filename} (ID {entry.image.id})")
    print(f"{len(built.entries)} images checked, written: {', '.join(str(p) for p in written)}")
    print("Flashing is not implemented yet: see docs/validation.md.")


def cmd_backup(args: argparse.Namespace) -> None:
    device = get_device(args.device)
    parsed = settings.parse(args.extract_dir / "settings.xml")
    loader = plan.select_loader(parsed, device, Ddr(args.ddr))
    manifest = backup.run(device, args.extract_dir / loader, args.out)
    print(f"{len(manifest['files'])} files saved in {args.out}, checksums in {backup.MANIFEST}")
    print("This backup contains the phone's IMEI and calibration data: never share it.")


def cmd_verify(args: argparse.Namespace) -> None:
    broken = backup.verify(args.backup_dir)
    if broken:
        raise backup.BackupError(f"{len(broken)} file(s) changed or missing: {broken}")
    print(f"{args.backup_dir}: every file matches {backup.MANIFEST}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="opmsm", description="Prepare a OnePlus MSM restore on macOS or Linux."
    )
    commands = root.add_subparsers(dest="command", required=True)

    decrypt = commands.add_parser("decrypt", help="extract an MSM .ops package")
    decrypt.add_argument("ops", type=Path)
    decrypt.add_argument("--out", type=Path, default=Path("extract"))
    decrypt.set_defaults(run=cmd_decrypt)

    inspect = commands.add_parser("inspect", help="describe an extracted package")
    inspect.add_argument("extract_dir", type=Path)
    inspect.set_defaults(run=cmd_inspect)

    build = commands.add_parser("plan", help="check images and write rawprogram files for one RAM type")
    build.add_argument("extract_dir", type=Path)
    build.add_argument("--device", required=True, choices=sorted(DEVICES))
    build.add_argument("--ddr", required=True, choices=[d.value for d in Ddr])
    build.add_argument("--out", type=Path, default=Path("plan"))
    build.set_defaults(run=cmd_plan)

    save = commands.add_parser("backup", help="read-only full backup over EDL (all partitions but userdata)")
    save.add_argument("extract_dir", type=Path, help="extracted package, for its Firehose loader")
    save.add_argument("--device", required=True, choices=sorted(DEVICES))
    save.add_argument("--ddr", required=True, choices=[d.value for d in Ddr], help="selects the Firehose loader")
    save.add_argument("--out", type=Path, required=True)
    save.set_defaults(run=cmd_backup)

    check = commands.add_parser("verify", help="check a backup against its checksums")
    check.add_argument("backup_dir", type=Path)
    check.set_defaults(run=cmd_verify)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        args.run(args)
    except (plan.PlanError, backup.BackupError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
