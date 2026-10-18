# opmsm — agent instructions

## Project

Open-source replacement for OnePlus MsmDownloadTool on macOS and Linux. Python 3.10+, managed
with uv. Code in `src/opmsm`, tests in `tests`.

## Commands

| Task | Command |
|---|---|
| Install / update dependencies | `uv sync` |
| Tests | `uv run pytest` |
| CLI | `uv run opmsm --help` |

## Rules

- Safety first: any doubt about an image, a partition or the RAM type aborts with `PlanError`.
  Never add a fallback that guesses.
- Nothing writes to a phone until the step is marked validated in `docs/validation.md`.
- oppo_decrypt has no license: never copy its code, only fetch it at the pinned commit
  (`src/opmsm/opscrypto.py`) and check its SHA-256.
- Device facts in `src/opmsm/devices.py` must cite their source in a comment.
- Package layouts in tests are synthetic until confirmed on a real package: say so in the test.
