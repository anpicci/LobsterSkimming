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
TSTAMP2 = datetime.datetime.now().strftime('%Y_%m_%d')

top_dir = subprocess.check_output(["git","rev-parse","--show-toplevel"])
top_dir = top_dir.strip()

sandbox_location = os.path.join(top_dir,"CMSSW_10_6_19_patch2")
print(sandbox_location)

testing = True
#testing = False

step = "skims"
tag = "data/NAOD_ULv9_new-lepMVA/UL2018/Full"               # Not used if in "testing" mode
ver = "v1"

#cfg_name = "mc_background_samples.cfg"
cfg_name = "mc_signal_samples.cfg"
#cfg_name = "data_samples.cfg"
cfg_fpath = os.path.join(top_dir,"topcoffea/topcoffea/cfg",cfg_name)
print(cfg_fpath)
# Only process json files that match these regexs (empty list matches everything)
match = []
# match = ['DoubleEG_F-UL2016\\.json']
# match = ['MuonEG_B-UL2017\\.json']

skim_cut = "'nMuon+nElectron >=1 && Sum$( Muon_looseId && Muon_miniPFRelIso_all < 0.4 && Muon_sip3d <8) + Sum$(Electron_miniPFRelIso_all < 0.4 && Electron_sip3d <8 && Electron_mvaFall17V2noIso_WPL) >=1'"

master_label = 'EFT_{step}_{tstamp}'.format(step=step,tstamp=TSTAMP1)
workdir_path = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="/tmpscratch/users/$USER")
plotdir_path = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="~/www/lobster")
output_path  = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="/store/user/$USER")

if testing:
    workdir_path = "{path}/{step}/test/lobster_test_{tstamp}".format(step=step,tstamp=TSTAMP1,path="/tmpscratch/users/$USER")
    plotdir_path = "{path}/{step}/test/lobster_test_{tstamp}".format(step=step,tstamp=TSTAMP1,path="~/www/lobster")
    output_path  = "{path}/{step}/test/lobster_test_{tstamp}".format(step=step,tstamp=TSTAMP1,path="/store/user/$USER")

# Different xrd src redirectors depending on where the inputs are stored
#xrd_src = "ndcms.crc.nd.edu"            # Use this for accessing samples from the GRID
#xrd_src = "cmsxrootd.fnal.gov"          # Only use this if the ND XCache is giving troubles
xrd_src = "deepthought.crc.nd.edu"      # Use this for accessing samples from ND T3

xrd_dst = "deepthought.crc.nd.edu"
#print("HERE!!!")
#print("root://{host}//store/".format(host=xrd_src))
storage_base = StorageConfiguration(
    input=[
        "root://{host}//store/".format(host=xrd_src)  # Note the extra slash after the hostname
        #"root://deepthought.crc.nd.edu/"
    ],
    output=[
        "hdfs://eddie.crc.nd.edu:19000{path}".format(path=output_path),
        "root://{host}/{path}".format(host=xrd_dst,path=output_path),    # Note the extra slash after the hostname
    ],
    disable_input_streaming=True,
)


storage_cmssw = StorageConfiguration(
    output = [
        "hdfs://eddie.crc.nd.edu:19000{path}".format(path=output_path),
        "root://{host}/{path}".format(host=xrd_dst,path=output_path),
    ],
    disable_input_streaming=True,
)

storage = storage_base

# See tools/utils.py for dict structure of returned object
cfg = read_cfg(cfg_fpath,match=match)

cat = Category(
    name='processing',
    cores=1,
    memory=1500,
    disk=4500,
)

wf = []
for sample in sorted(cfg['jsons']):
    jsn = cfg['jsons'][sample]
    print "Sample: {}".format(sample)
    for fn in jsn['files']:
        print "\t{}".format(fn)
    files = [x.replace('/store/','') for x in jsn['files']]
    module_name = ''
    if 'HIPM_UL2016' in sample:
        module_name = 'lepMVA_2016_preVFP'
    elif 'UL2017' in sample:
        module_name = 'lepMVA_2017'
    elif 'UL2018' in sample:
        module_name = 'lepMVA_2018'
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

    ds = ds_base
    cmd = ['python','skim_wrapper.py']
    cmd.extend(['--cut',skim_cut])
    cmd.extend(['--module',module_name])
    cmd.extend(['--out-dir','.'])
    cmd.extend(['@inputfiles'])
    skim_wf = Workflow(
        label=sample.replace('-','_'),
        sandbox=cmssw.Sandbox(release=sandbox_location),
        dataset=ds,
        category=cat,
        extra_inputs=['skim_wrapper.py',os.path.join(sandbox_location,'src/PhysicsTools/NanoAODTools/scripts/haddnano.py')],
        outputs=['output.root'],
        command=' '.join(cmd),
        merge_command='python haddnano.py @outputfiles @inputfiles',
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
        dashboard=False, # Important to avoid a crash caused by out of date WMCore
        bad_exit_codes=[127, 160],
        log_level=1,
        payload=10,
        xrootd_servers=[
            #'ndcms.crc.nd.edu',
            # 'cmsxrootd.fnal.gov',
             'deepthought.crc.nd.edu'
        ]
    )
)
