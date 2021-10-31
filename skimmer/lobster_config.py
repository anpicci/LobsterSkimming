import datetime
import os
import sys
import shutil
import subprocess

from lobster import cmssw
from lobster.core import AdvancedOptions, Category, Config, Dataset, ParentDataset, StorageConfiguration, Workflow

sys.path.append(os.path.split(__file__)[0])
from tools.utils import read_cfg


TSTAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M')

top_dir = subprocess.check_output(["git","rev-parse","--show-toplevel"])
top_dir = top_dir.strip()

sandbox_location = os.path.join(top_dir,"CMSSW_9_4_6")

testing = True

step = "skims"
tag = "NanoAOD_ULv8"    # Not used if in "testing" mode
ver = "v1"

cfg_name = "data_samples.cfg"
cfg_fpath = os.path.join(top_dir,"topcoffea/topcoffea/cfg",cfg_name)

skim_cut = "'nMuon+nElectron >=2 && Sum$( Muon_looseId && Muon_miniPFRelIso_all < 0.4 && Muon_sip3d <8) + Sum$(Electron_miniPFRelIso_all < 0.4 && Electron_sip3d <8 && Electron_mvaFall17V2noIso_WPL) >=2'"

master_label = 'EFT_{step}_{tstamp}'.format(step=step,tstamp=TSTAMP)
workdir_path = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="/tmpscratch/users/$USER")
plotdir_path = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="~/www/lobster")
output_path  = "{path}/{step}/{tag}/{ver}".format(step=step,tag=tag,ver=ver,path="/store/user/$USER")

if testing:
    workdir_path = "{path}/{step}/test/lobster_test_{tstamp}".format(step=step,tstamp=TSTAMP,path="/tmpscratch/users/$USER")
    plotdir_path = "{path}/{step}/test/lobster_test_{tstamp}".format(step=step,tstamp=TSTAMP,path="~/www/lobster")
    output_path  = "{path}/{step}/test/lobster_test_{tstamp}".format(step=step,tstamp=TSTAMP,path="/store/user/$USER")

# Turns out it might matter
xrd_src = "ndcms.crc.nd.edu"
xrd_dst = "deepthought.crc.nd.edu"

storage = StorageConfiguration(
    input=[
        "root://{host}//store/".format(host=xrd_src)  # Note the extra slash after the hostname
    ],
    output=[
        "hdfs://eddie.crc.nd.edu:19000",
        "root://{host}/{path}".format(host=xrd_dst,path=output_path),    # Note the extra slash after the hostname
    ],
    disable_input_streaming=True,
)

# See tools/utils.py for dict structure of returned object
cfg = read_cfg(cfg_fpath)

cat = Category(
    name='processing',
    cores=1,
    memory=3000,
    disk=4000,
)

wf = []
for sample in sorted(cfg['jsons']):
    jsn = cfg['jsons'][sample]
    print "Sample: {}".format(sample)
    for fn in jsn['files']:
        print "\t{}".format(fn)
    cmd = ['python','skim_wrapper.py','--cut={}'.format(skim_cut),'.','@inputfiles']
    skim_wf = Workflow(
        label=sample.replace('-','_'),
        sandbox=cmssw.Sandbox(release=sandbox_location),
        dataset=Dataset(
            files=[x.replace('/store/','') for x in jsn['files']],
            files_per_task=1
        ),
        category=cat,
        extra_inputs=['skim_wrapper.py'],
        outputs=['output.root'],
        command=' '.join(cmd),
        merge_size=-1,
        globaltag=False,    # To avoid autosense crash (can be anything, just not 'None')
    )
    wf.extend([skim_wf])

config = Config(
    label=master_label,
    workdir=workdir_path,
    plotdir=plotdir_path,
    storage=storage,
    workflows=wf,
    advanced=AdvancedOptions(
        dashboard=False,
        bad_exit_codes=[127, 160],
        log_level=1,
        payload=10,
        xrootd_servers=[
            'ndcms.crc.nd.edu',
            'deepthought.crc.nd.edu'
        ]
    )
)
