# opmsm

Restore a OnePlus phone from its official MSM package on **macOS or Linux**, without the
Windows-only MsmDownloadTool.

> **Status: preparation only.** opmsm decrypts a package, checks every image and builds the
> flash plan for your RAM type (checked on the EU 8T package `kebab_15_E.12_201110`). It does not write to a phone yet: the write path has never been
> validated on real hardware (see [docs/validation.md](docs/validation.md)). Until it is, use
> MsmDownloadTool to actually flash.

## Why

MsmDownloadTool is the only official way back to stock once a OnePlus is stuck, and it only runs
on Windows. The building blocks for an open-source replacement already exist:

- [bkerler/oppo_decrypt](https://github.com/bkerler/oppo_decrypt) decrypts `.ops` packages;
- [bkerler/edl](https://github.com/bkerler/edl) speaks Qualcomm EDL (Sahara + Firehose) and
  implements the OnePlus authentication, including the OnePlus 8T (project `19805`).

What is missing is the part that makes MsmDownloadTool safe: picking the right images for the
phone's RAM. The OnePlus 8T shipped with DDR4 and DDR5, and flashing the bootloader (`xbl`) for
the wrong one hard-bricks the phone. opmsm makes that choice explicit and refuses anything
ambiguous.

## Supported devices

| Device | Codename | Models | Notes |
|---|---|---|---|
| OnePlus 8T | `kebab` | KB2000, KB2001, KB2003, KB2005 | DDR4: `xbl`, `xbl_config`; DDR5: `xbl_lp5`, `xbl_config_lp5` |

The T-Mobile 8T (`kebabt`, KB2007) is not supported yet: it has its own EDL project id (`20809`)
and its own MSM package (`KB09CB`), so it must never be flashed with the `kebab` profile. It can be
added as a separate profile once validated on a real KB2007.

## Usage

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv run opmsm decrypt kebab_15_E.12_201110.ops --out extract
uv run opmsm inspect extract
uv run opmsm plan extract --device kebab --ddr ddr4 --out plan
```

`decrypt` downloads `opscrypto.py` from oppo_decrypt at a pinned commit and checks its SHA-256
before running it (oppo_decrypt has no license, so its code is not copied here).

`plan` verifies the Firehose loader, the presence and SHA-256 of every image, selects the
DDR-dependent images and writes one `rawprogram<LUN>.xml` per UFS LUN. It stops on any doubt:
unknown package layout, missing or extra DDR variant, missing file, checksum mismatch.

### Full backup of a working phone

Before experimenting (custom ROM, bootloader unlock), save the phone's exact state over EDL. It is
read-only, and once `restore` is validated it brings the phone back to that state directly,
without going through an old MSM release and its chain of OTA updates.

```sh
brew install libusb          # macOS, once: USB access for edl
uv run opmsm backup extract --device kebab --ddr ddr4 --out backups/my-8t-oos14
uv run opmsm verify backups/my-8t-oos14
```

`backup` reads every partition of every UFS LUN except `userdata` (about 10 to 15 GB), with the
GPTs and rawprogram files, and records a SHA-256 for each file. `--ddr` picks the Firehose
loader of the package that matches the phone's RAM. Put the phone in EDL first:
powered off, hold Volume Up + Volume Down and plug the cable.

**A backup contains the phone's IMEI and calibration data** (`modemst`, `fsg`, `persist`). It
belongs to that phone only: never share it, never write it to another phone.

### Knowing your RAM type

Read it while the phone still boots, from Android, recovery or a booted LineageOS recovery:

```sh
adb shell getprop ro.boot.ddr_type        # 0 = DDR4, 1 = DDR5
adb shell cat /proc/devinfo/ddr_type      # fallback
```

Reading it over EDL, for a phone that no longer boots, is on the roadmap.

## Development

```sh
uv run pytest
```

## License

GPL-3.0-or-later, to stay compatible with bkerler/edl.
