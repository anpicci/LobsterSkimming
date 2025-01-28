import datetime
import os
import sys
import shutil
import subprocess

from lobster import cmssw
from lobster.core import AdvancedOptions, Category, Config, Dataset, ParentDataset, StorageConfiguration, Workflow

sys.path.append(os.path.split(__file__)[0])
from tools.utils import read_cfg

TSTAMP1 = datetime.datetime.now().strftime('%Y%m%d_%H%M')
startingday = datetime.datetime.now().strftime('%y%m%d')

top_dir = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode("utf-8").strip()
print(top_dir)

sandbox_location = os.path.join(top_dir,"CMSSW_14_0_6")
#sandbox_location = "/afs/crc.nd.edu/user/a/apiccine/Lobster-With-Conda/LobsterSkimming/CMSSW_14_0_6"

testing = True

step = "run3skims"
tag = "data/NAOD_ULv12_lepMVA-run3/2022/Full"               # Not used if in "testing" mode
#ver = "v1"
ver = "v{}".format(startingday)

cfg_name = "2022_data_samples.cfg"
#cfg_name = "mc_signal_samples.cfg"

cfg_fpath = os.path.join(top_dir,"topeft/input_samples/cfgs",cfg_name)

# Only process json files that match these regexs (empty list matches everything)
#match = ['.*UL2018\\.json']
match = ['.*EGamma.*22Sep2023\\.json']
# match = ['DoubleEG_F-UL2016\\.json']
# match = ['MuonEG_B-UL2017\\.json']

skim_cut = "'nMuon+nElectron >=2 && Sum$( Muon_looseId && Muon_miniPFRelIso_all < 0.4 && Muon_sip3d <8) + Sum$(Electron_miniPFRelIso_all < 0.4 && Electron_sip3d <8 && Electron_mvaFall17V2noIso_WPL) >=2'"

master_label = '{step}_{tstamp}'.format(step=step,tstamp=TSTAMP1)
workdir_path = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="/tmpscratch/users/$USER")
plotdir_path = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="~/www/lobster")
output_path  = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="/store/user/$USER")

if testing:
    master_label = '{step}_lobPY3_test_{tstamp}'.format(step=step,tstamp=TSTAMP1)
    workdir_path = "{path}/{step}/test/lobster_skimtest_{tstamp}".format(step=step,tstamp=TSTAMP1,path="/tmpscratch/users/$USER")
    plotdir_path = "{path}/{step}/test/lobster_skimtest_{tstamp}".format(step=step,tstamp=TSTAMP1,path="~/www/lobster")
    output_path  = "{path}/{step}/test/lobster_skimtest_{tstamp}".format(step=step,tstamp=TSTAMP1,path="/store/user/$USER")

# Different xrd src redirectors depending on where the inputs are stored
#xrd_src = "ndcms.crc.nd.edu"            # Use this for accessing samples from the GRID
#xrd_src = "cmsxrootd.fnal.gov"          # Only use this if the ND XCache is giving troubles
xrd_src = "hactar01.crc.nd.edu"      # Use this for accessing samples from ND T3
xrd_dst = "hactar01.crc.nd.edu"

storage_base = StorageConfiguration(
    input=[
        "root://{host}//".format(host=xrd_src)  # Note the extra slash after the hostname
    ],
    output=[
        f"file:///cms/cephfs/data/{output_path}",
        f"root://{xrd_dst}/{output_path}",
    ],
    #disable_input_streaming=True,
)


storage_cmssw = StorageConfiguration(
    output=[
        f"file:///cms/cephfs/data/{output_path}",
        f"root://{xrd_dst}/{output_path}",
    ],
    #disable_input_streaming=True,
)

storage = storage_cmssw

# See tools/utils.py for dict structure of returned object
cfg = read_cfg(cfg_fpath,match=match)
#print("cfg", cfg)
cat = Category(
    name='processing',
    cores=1,
    memory=1500,
    disk=4500,
)

wf = []
for sample in sorted(cfg['jsons']):
    jsn = cfg['jsons'][sample]
    print(("Sample: {}".format(sample)))
    for fn in jsn['files']:
        print(("\t{}".format(fn)))
    files = [x.replace('/store/','') for x in jsn['files']]
    module_name = ''
    if 'HIPM_UL2016' in sample:
        module_name = 'lepMVA_2016_preVFP'
    elif 'UL2017' in sample:
        module_name = 'lepMVA_2017'
    elif 'UL2018' in sample:
        module_name = 'lepMVA_2018'
    elif sample.startswith('202'):
        module_name = 'lepMVA'
    else:
        module_name = 'lepMVA_2016'

    ds_base = Dataset(
        files=files,
        files_per_task=1
    )

    ds_cmssw = cmssw.Dataset(
        dataset=jsn['path'],
        lumis_per_task=1,   # Since file_based is true, this will be files_per_task
        file_based=True
    )

    ds = ds_cmssw

    cmd = ['python3','skim_wrapper.py']
    cmd.extend(['--cut',skim_cut])
    cmd.extend(['--module',module_name])
    cmd.extend(['--out-dir','.'])
    cmd.extend(['@inputfiles'])
    print("\n\n\n")
    print(("Command to execute:", cmd))
    print("\n\n\n")
    skim_wf = Workflow(
        label=sample.replace('-','_'),
        sandbox=cmssw.Sandbox(release=sandbox_location),
        dataset=ds_cmssw,
        category=cat,
        extra_inputs=['skim_wrapper.py'], #,os.path.join(sandbox_location,'src/PhysicsTools/NanoAODTools/scripts/haddnano.py')],
        outputs=['output.root'],
        command=' '.join(cmd),
        #merge_command='python haddnano.py @outputfiles @inputfiles',
        merge_command='haddnano.py @outputfiles @inputfiles',
        merge_size='537M',
        globaltag=False,    # To avoid autosense crash (can be anything, just not None)
        cleanup_input=False
    )
    wf.extend([skim_wf])

config = Config(
    label=master_label,
    workdir=workdir_path,
    plotdir=plotdir_path,
    storage=storage,
    workflows=wf,
    advanced=AdvancedOptions(
	bad_exit_codes=[127, 160],
        log_level=1,
        payload=10,
	osg_version='3.6',
        #threshold_for_failure=100,
	#threshold_for_skipping=100,
    )
)
    
#config = Config(
#    label=master_label,
#    workdir=workdir_path,
#    plotdir=plotdir_path,
#    storage=storage,
#    workflows=wf,
#    advanced=AdvancedOptions(
#        dashboard=False, # Important to avoid a crash caused by out of date WMCore
#        bad_exit_codes=[127, 160],
#        log_level=1,
#        payload=10,#3        xrootd_servers=[
#            'ndcms.crc.nd.edu',
#            # 'cmsxrootd.fnal.gov',
#            # 'deepthought.crc.nd.edu'
#        ]
#    )
#)
