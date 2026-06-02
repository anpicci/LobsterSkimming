# Run3 lobster config compatibility check

Checked against the latest `skimmer/lobster_config.py` available from the `run3-mva-anpicci` branch on GitHub.

## Supported in the integrated config

- `INPUT_MODE = "dbs"` and `INPUT_MODE = "files"` dataset selection modes.
- Local and remote storage prefixes using `PROTOCOL_LOCAL`, `PROTOCOL_REMOTE`, `SRC_*`, and `DST_*` knobs.
- Run3 `TARGET` behavior, including `SR` mode with the opposite-sign two-lepton veto and non-`SR` mode with only the `nlep >= 2` requirement.
- Run3 `TYPE` behavior, including dynamic config-name construction for `data` versus non-data samples when `cfg_name` is omitted from a profile.
- Run3 default labels and paths using `{STEP}_{TARGET}`.
- Profile-driven CMSSW sandbox release, with `run3_mva_anpicci` using `CMSSW_14_0_6`.
- File listing diagnostics, remote command diagnostics, and output destination diagnostics.
- Era-aware lepMVA module selection for Run2 and Run3 sample names, including the Run3 `lepMVA_2016` fallback module for unmatched sample names.
- DBS XRootD server wiring when `INPUT_MODE == "dbs"`.
- Advanced options from the latest Run3 config, including `threshold_for_failure=10` and `threshold_for_skipping=10`.

## Compatibility notes

The integrated config keeps the profile abstraction for Run2/Run3 coexistence. Run3-specific defaults live in the `run3_mva_anpicci` profile rather than as top-level global constants.
