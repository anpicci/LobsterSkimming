# LobsterSkimming
CMS skimming code that's been lobsterized for use on ND's computing resources


### Setup dependencies
Run the python setup script
```
python setup.py
```
This script will set up a basic CMSSW release and check out the necessary [NanoAOD skimming](https://github.com/cms-nanoAOD/nanoAOD-tools) package. The script also automatically gets the cfg and json directories from the [TopEFT/topeft Run3 branch](https://github.com/TopEFT/topeft/tree/run3_test_mmerged) repo.

Setup configuration now mirrors lobster runtime profiles.

At the top of `setup.py`, select `ACTIVE_SETUP_PROFILE` and fallback values in `SETUP_PROFILES`.
Optionally, edit `setup_profiles.md` to provide external profile values loaded by `setup.py`.

Each setup profile provides:

- `cmssw_release`
- `scram_arch`
- `topeft_tag`
- `topeft_url`
- `cmgtools_url`
- `cmgtools_branch`
- `nanoaodtools_url`
- `nanoaodtools_branch`

The CMSSW release that is used to construct the environment that actually runs the skimming job does not necessarily have to match the CMSSW release that is used to provide the dependencies for the lobster program itself. So changing what CMSSW release is used for doing the actual skimming should not have to result in a change to the CMSSW release used for your lobster environment.

### Running the code
Assuming that you installed lobster in a dedicated conda/mamba environment (see [this lobster project branch](https://github.com/anpicci/lobster/tree/lobster-python3-run3))
- Make sure to have a working CMSSW release in your local `LobsterSkimming` area:
```
cd CMSSW_X_Y_Z/src
cmsenv
```
- In a new clean shell, activate your lobster conda/mamba environment
```
conda activate lobster_env
## mamba activate lobster_env
```
- Configure `ACTIVE_PROFILE` and related knobs in `skimmer/lobster_config.py`, then run
```
lobster process skimmer/lobster_config.py
```

### Configuring the lobster job
The main configuration option in `skimmer/lobster_config.py` is now `ACTIVE_PROFILE`, which selects a coherent set of defaults:

- `run2_el9_skims`: Run2-oriented defaults on EL9
- `run3_mva_anpicci`: Run3 lepMVA defaults

There are now two supported configuration paths:

1. Edit embedded Python variables directly in `skimmer/lobster_config.py` (recommended for local workflow control).
2. Edit `skimmer/lobster_profiles.md` to define profile defaults externally in a markdown file loaded by the script.

Key embedded knobs include:

- `ACTIVE_PROFILE`
- `INPUT_MODE`
- `STEP`
- `MATCH`
- `SRC_REMOTE`, `SRC_LOCAL`, `DST_REMOTE`, `DST_LOCAL`
- `WORKDIR_BASE`
- `SANDBOX_RELEASE`

The `step`, `tag`, and `ver` variables are used to define output and work directory names. If `TESTING=True` in `skimmer/lobster_config.py`, output paths are redirected to a timestamped test location.
