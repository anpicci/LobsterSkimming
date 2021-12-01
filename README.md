# LobsterSkimming
CMS skimming code that's been lobsterized for use on ND's computing resources


### Setup dependencies
Run the python setup script
```
python setup.py
```
This script will setup a basic CMSSW release and checkout the necessary [NanoAOD skimming](https://github.com/cms-nanoAOD/nanoAOD-tools) package. The script also automatically gets the cfg and json directories from the [TopEFT/topcoffea](https://github.com/TopEFT/topcoffea/tree/master) repo.

The repo is currently setup to automatically generate and use a `CMSSW_10_6_19_patch2` release, but can be changed to use a different release. The simplest method would be to modify the [setup.py](https://github.com/Andrew42/LobsterSkimming/blob/master/setup.py) script, re-run it and then also update the [lobster_config.py](https://github.com/Andrew42/LobsterSkimming/blob/master/skimmer/lobster_config.py) config by changing the `sandbox_location` variable.

The CMSSW release that is used to construct the environment that actually runs the skimming job does not have to necessarily match the CMSSW release that is used to provide the dependencies for the lobster program itself. So changing what CMSSW release is used for doing the actual skimming should not have to result in a change to the CMSSW release used for your lobster environment.

### Running the code
- Make sure to do a `cmsenv` in a CMSSW release compatible with your lobster installation
```
cd CMSSW_X_Y_Z/src
cmsenv
```
- Activate your lobster environment
```
source ~/.lobster/bin/activate
```
- Run the code
```
lobster process lobster_config.py
```

### Configuring the lobster job
The main configuration option in `lobster_config.py` is the choice of the `cfg_name` variable. This should correspond to one of the cfg names from topcoffea cfg files and will determine which dataset samples should be run over. The `step`, `tag`, and `ver` variables are used to define the directory names of the lobster job. If `testing=True`, then only the `step` variable will be used and the output directories will instead be changed to something of the form `$USER/{step}/test/lobster_test_{tstamp}`, where `{tstamp}` will correspond to a datetime timestamp of when the lobster job was started.
