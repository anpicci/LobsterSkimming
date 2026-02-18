# Run2 + Run3 Integration Notes

This branch keeps one lobster entrypoint and supports both run eras through profile defaults.

## What changed from the previous PR

Instead of environment-variable-driven runtime and setup knobs, configuration now uses:

1. Embedded Python profile variables in `setup.py` and `skimmer/lobster_config.py`.
2. Optional external markdown profile definitions in `setup_profiles.md` and `skimmer/lobster_profiles.md`.

This keeps behavior explicit in-repo and avoids shell-env coupling.

## Runtime profile selection

In `skimmer/lobster_config.py`, set:

- `ACTIVE_PROFILE = "run2_el9_skims"` or
- `ACTIVE_PROFILE = "run3_mva_anpicci"`

The script loads profile defaults from:

- Built-in `PROFILES` dict (fallback)
- `skimmer/lobster_profiles.md` (if present)

## Setup configuration

In `setup.py`, set `ACTIVE_SETUP_PROFILE` to choose the setup preset.

Setup profiles are loaded from:

- Built-in `SETUP_PROFILES` dict (fallback)
- `setup_profiles.md` (if present)

Each setup profile includes:

- `cmssw_release`
- `scram_arch`
- `topeft_tag`
- `topeft_url`
- `cmgtools_url`
- `cmgtools_branch`
- `nanoaodtools_url`
- `nanoaodtools_branch`

## Merge intent

Single source of truth with explicit script-level knobs and optional markdown profile file to reduce branch drift while keeping configuration easy to audit.
