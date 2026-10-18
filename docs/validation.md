# Validation status and roadmap

opmsm writes to the bootloader partitions of a phone. A mistake there is not recoverable by the
user, so each step is validated on real hardware before the next one is enabled.

| Step | Risk | Status |
|---|---|---|
| Decrypt an 8T `.ops` package | none | **done** on `kebab_15_E.12_201110` (EU) |
| Describe the package (`inspect`) | none | **done** on the same package |
| Build and check the flash plan (`plan`) | none | **done** for DDR4 and DDR5: 61 images, SHA-256 match |
| Confirm the real `settings.xml` layout, in particular how DDR variants are stored | none | **done**, see below |
| EDL handshake and OnePlus authentication from macOS | none | open, first real run of `backup` |
| Package flash plan includes the GPT patches as MSM applies them | none | patches are copied, not yet checked against MSM |
| UFS provisioning (`provision_*.xml`) | very high | **excluded on purpose**: done at the factory, a wrong one can make the UFS unusable for good |
| Full read-only backup (`backup`, `verify`) | none | implemented, edl faked in tests |
| Read the RAM type over EDL | none | open, method unknown |
| Restore a full backup to the same phone (`restore`) | high | not implemented |
| Flash an MSM package through edl (`qfil` emulation) on a test phone | high | not implemented |

Restoring a backup comes before flashing a package: the images are the phone's own, read from it,
so the DDR choice and the `super` layout are right by construction.

## Known facts

- bkerler/edl lists the OnePlus 8T as tested **read-only**: writing has never been reported.
- MsmDownloadTool detects the RAM type itself ("Automatic detection of DDR failed" when it
  cannot) and selects `xbl`/`xbl_lp5` accordingly; how it reads it is not documented.
- MsmDownloadTool pitfalls seen on an 8T (EU package `kebab_15_E.12_201110`): "Failed to send
  lite DP" until "Use Lite Firehose" was unchecked and the phone fully powered off between tries;
  "Unsupported Target O2" until the target was set to EU.

## Package layout (kebab_15_E.12_201110)

- `SAHARA` lists three Firehose loaders, indexed by `DPIndex`: `0` lite, `1`
  `prog_firehose_ddr.elf` (DDR4), `2` `prog_firehose_ddr_lp5.elf` (DDR5). The loader depends on
  the RAM type too, so `backup` takes `--ddr`.
- Each `Program<N>` holds `<program>` partitions with `<Image>` children. Only `xbl_a` and
  `xbl_config_a` (LUN 1) are `multiImage="true"`, with `ID="65540"` for the `_lp5` image and
  `ID="4"` for the DDR4 one. `xbl_b` and `xbl_config_b` (LUN 2) carry no image: MSM writes the
  bootloader to slot A only.
- `Patch<N>` holds the GPT patches of each LUN.
- `Sha256` is computed over the image zero-padded to a 4 KiB sector (as opscrypto does).
- `BasicInfo` has `Project="19805"` and `AutoDetectDDR="true"`.

## Next step

First real `opmsm backup` of a working 8T, to validate the EDL authentication from macOS.

First attempt (macOS, 2026-10-18): the Mac listed `QUSB_BULK` (05c6:9008) but edl stayed on
"Waiting for the device" until the phone left EDL and booted. Notes for the next try:

- edlclient asks libusb1 for `libusb-1.0.so` on darwin and gets no backend; pyusb then falls back
  to its default lookup, which finds `/opt/homebrew/lib/libusb-1.0.dylib`. Probably harmless.
- `--debugmode` writes `logs/log.txt` in the current directory and crashes if `logs/` is missing.
- The phone was behind a USB 2.0 hub and a DisplayLink dock: retry on a port of the Mac itself,
  with edl started before the phone enters EDL.
