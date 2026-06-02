# Lobster profiles

This file defines profile defaults used by `skimmer/lobster_config.py`.

## run2_el9_skims
- year: 2018
- step: skims
- type: background
- target: SR
- tag: data/NAOD_ULv12_lepMVA-run2/2018
- cfg_name: ND_UL18_background_samples.cfg
- sandbox_release: CMSSW_10_6_19_patch2
- default_module: lepMVA_2018

## run3_mva_anpicci
- year: 2023BPix
- step: skimmed
- type: background
- target: SR
- tag: background/NAOD_ULv12_lepMVA-run3/2023BPix
- cfg_name: ND_2023BPix_background_samples.cfg
- sandbox_release: CMSSW_14_0_6
- default_module: lepMVA_2016
