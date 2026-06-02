import datetime
import os
import sys
import subprocess

from lobster import cmssw
from lobster.core import AdvancedOptions, Category, Config, Dataset, StorageConfiguration, Workflow

sys.path.append(os.path.split(__file__)[0])
from tools.utils import read_cfg


# =============================================================================
# USER KNOBS (edit here)
# =============================================================================
TESTING = False

# Primary selection knob (embedded Python variable, no env var needed)
ACTIVE_PROFILE = "run2_el9_skims"

# Optional external markdown profile file.
# If this file exists and defines ACTIVE_PROFILE, those values are used.
PROFILE_MARKDOWN_FILE = os.path.join(os.path.split(__file__)[0], "lobster_profiles.md")

# Runtime knobs
INPUT_MODE = "files"  # "dbs" or "files"
PROTOCOL_LOCAL = "file://"
PROTOCOL_REMOTE = "root://"
STEP = "skims"
TYPE = "background"
TARGET = "SR"
MATCH = []  # e.g. [r".*TTLL\_MLL-50.*\.json"]

# XRootD endpoints
SRC_REMOTE = "cmsxrootd.crc.nd.edu"
SRC_LOCAL = "/cms/cephfs/data"
DST_REMOTE = "cmsxrootd.crc.nd.edu"
DST_LOCAL = "/cms/cephfs/data"
WORKDIR_BASE = "/tmpscratch/users/$USER"

# Fallback profile defaults (used if markdown file is absent)
PROFILES = {
    "run2_el9_skims": {
        "year": "2018",
        "step": "skims",
        "type": "background",
        "target": "SR",
        "tag": "data/NAOD_ULv12_lepMVA-run2/2018",
        "cfg_name": "ND_UL18_background_samples.cfg",
        "sandbox_release": "CMSSW_10_6_19_patch2",
        "default_module": "lepMVA_2018",
    },
    "run3_mva_anpicci": {
        "year": "2023BPix",
        "step": "skimmed",
        "type": "background",
        "target": "SR",
        "tag": "background/NAOD_ULv12_lepMVA-run3/2023BPix",
        "cfg_name": "ND_2023BPix_background_samples.cfg",
        "sandbox_release": "CMSSW_14_0_6",
        "default_module": "lepMVA_2016",
    },
}

WRAPPER = "skim_wrapper.py"


# =============================================================================
# HELPERS
# =============================================================================
def parse_markdown_profiles(md_path):
    """Parse a simple markdown profile file with sections and '- key: value' lines."""
    if not os.path.exists(md_path):
        return {}

    parsed = {}
    current = None
    with open(md_path) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("## "):
                current = line[3:].strip()
                parsed[current] = {}
                continue

            if current and line.startswith("- ") and ":" in line:
                content = line[2:]
                key, value = content.split(":", 1)
                parsed[current][key.strip()] = value.strip()

    return parsed


def default_tag(sample_type, year, active_profile):
    if active_profile == "run3_mva_anpicci":
        return f"{sample_type}/NAOD_ULv12_lepMVA-run3/{year}"
    return f"data/NAOD_ULv12_lepMVA-run2/{year}"


def default_cfg_name(sample_type, year):
    if sample_type == "data":
        return f"{year}_data.cfg"
    return f"ND_{year}_{sample_type}_samples.cfg"


def make_skim_cut(target):
    el_req = (
        "Electron_pt>10 && Electron_miniPFRelIso_all<0.4 && Electron_sip3d<8 && "
        "(abs(Electron_eta + Electron_deltaEtaSC) < 1.4442 || "
        "abs(Electron_eta + Electron_deltaEtaSC) > 1.566)"
    )
    mu_req = "Muon_pt>10 && Muon_looseId && Muon_miniPFRelIso_all<0.4 && Muon_sip3d<8"
    ta_req = (
        "Tau_pt>20 && Tau_dxy<0.05 && Tau_dz<1 && "
        "Tau_idDeepTau2018v2p5VSe>1 && Tau_idDeepTau2018v2p5VSmu>3 && "
        "Tau_idDeepTau2018v2p5VSjet>2"
    )
    num_leps = f"(Sum$({el_req}) + Sum$({mu_req}) + Sum$({ta_req}))"
    net_charge = (
        f"(Sum$(Electron_charge*({el_req})) + Sum$(Muon_charge*({mu_req})) + "
        f"Sum$(Tau_charge*({ta_req})))"
    )
    os2l_veto = f"(({num_leps} != 2) || ({net_charge} != 0))"
    nlep_req = f"({num_leps} >= 2)"
    return f"{nlep_req} && {os2l_veto}" if target == "SR" else nlep_req


def pick_module(sample_name, default_module):
    if "HIPM_UL2016" in sample_name:
        return "lepMVA_2016_preVFP"
    if "UL2016" in sample_name:
        return "lepMVA_2016"
    if "UL2017" in sample_name:
        return "lepMVA_2017"
    if "UL2018" in sample_name:
        return "lepMVA_2018"
    if "2022" in sample_name or "2023" in sample_name:
        return "lepMVA"
    return default_module


# =============================================================================
# PROFILE SELECTION / VALIDATION
# =============================================================================
md_profiles = parse_markdown_profiles(PROFILE_MARKDOWN_FILE)
if md_profiles:
    PROFILES.update(md_profiles)

if ACTIVE_PROFILE not in PROFILES:
    raise ValueError(
        f"Unknown ACTIVE_PROFILE={ACTIVE_PROFILE!r}. Valid profiles: {', '.join(sorted(PROFILES))}"
    )

if INPUT_MODE not in ("dbs", "files"):
    raise ValueError(f"INPUT_MODE must be 'dbs' or 'files', got: {INPUT_MODE!r}")

profile_cfg = PROFILES[ACTIVE_PROFILE]
YEAR = profile_cfg["year"]
STEP = profile_cfg.get("step", STEP)
TYPE = profile_cfg.get("type", TYPE)
TARGET = profile_cfg.get("target", TARGET)
TAG = profile_cfg.get("tag", default_tag(TYPE, YEAR, ACTIVE_PROFILE))
CFG_NAME = profile_cfg.get("cfg_name", default_cfg_name(TYPE, YEAR))
SANDBOX_RELEASE = profile_cfg["sandbox_release"]
DEFAULT_MODULE = profile_cfg.get("default_module", "lepMVA_2016")
SKIM_CUT = make_skim_cut(TARGET)


# =============================================================================
# DERIVED PATHS / LABELS
# =============================================================================
SRC_PREFIX_LOCAL = PROTOCOL_LOCAL + SRC_LOCAL + "//"
DST_PREFIX_LOCAL = PROTOCOL_LOCAL + DST_LOCAL + "//"
SRC_PREFIX_REMOTE = PROTOCOL_REMOTE + SRC_REMOTE + "//"
DST_PREFIX_REMOTE = PROTOCOL_REMOTE + DST_REMOTE + "//"

TSTAMP1 = datetime.datetime.now().strftime("%Y%m%d_%H%M")
startingday = datetime.datetime.now().strftime("%y%m%d")
ver = f"v{startingday}"

try:
    top_dir = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).decode("utf-8").strip()
    sandbox_location = os.path.join(top_dir, SANDBOX_RELEASE)
    cfg_fpath = os.path.join(top_dir, "topeft", "input_samples", "cfgs", CFG_NAME)
except Exception as e:
    print("Error while determining top-level directory or cfg file path.")
    print("Please check your git repository and configuration.")
    print("Error details:")
    print(e)
    raise Exception("Failed to set up configuration due to the above error.")

mode_stamp = INPUT_MODE
step_label = f"{STEP}_{TARGET}" if TARGET else STEP
master_label = f"{step_label}_{ACTIVE_PROFILE}_{mode_stamp}_lobPY3_{TSTAMP1}"
workdir_path = f"{WORKDIR_BASE}/{step_label}/{TAG}/{ver}"
plotdir_path = f"~/www/lobster/{step_label}/{TAG}/{ver}"
output_path = f"/store/user/$USER/{step_label}/{TAG}/{ver}"

if TESTING:
    master_label = f"{step_label}_{ACTIVE_PROFILE}_{mode_stamp}_testlobPY3_{TSTAMP1}"
    workdir_path = f"{WORKDIR_BASE}/{step_label}/test/lobster_skimtest_{TSTAMP1}"
    plotdir_path = f"~/www/lobster/{step_label}/test/lobster_skimtest_{TSTAMP1}"
    output_path = f"/store/user/$USER/{step_label}/test/lobster_skimtest_{TSTAMP1}"

print(f"Selected ACTIVE_PROFILE = {ACTIVE_PROFILE}")
print(f"Using profile markdown file: {PROFILE_MARKDOWN_FILE}")
print(f"TYPE = {TYPE}")
print(f"TARGET = {TARGET}")
print(f"Sandbox location: {sandbox_location}")
print(f"Where is your cfg?\t {cfg_fpath}")
print(f"INPUT_MODE = {INPUT_MODE}")
print(f"SRC_PREFIX_LOCAL = {SRC_PREFIX_LOCAL}")
print(f"SRC_PREFIX_REMOTE = {SRC_PREFIX_REMOTE}")
print(f"DST_PREFIX_LOCAL = {DST_PREFIX_LOCAL}")
print(f"DST_PREFIX_REMOTE = {DST_PREFIX_REMOTE}")
print(f"{DST_PREFIX_LOCAL}{output_path}", "\n")
print(f"{DST_PREFIX_REMOTE}{output_path}", "\n")


# =============================================================================
# STORAGE (mode-dependent)
# =============================================================================
storage_dbs = StorageConfiguration(
    output=[f"{DST_PREFIX_REMOTE}{output_path}"],
    disable_input_streaming=False,
)

storage_files = StorageConfiguration(
    input=[f"{SRC_PREFIX_LOCAL}", f"{SRC_PREFIX_REMOTE}"],
    output=[f"{DST_PREFIX_LOCAL}{output_path}", f"{DST_PREFIX_REMOTE}{output_path}"],
    disable_input_streaming=False,
)

storage = storage_dbs if INPUT_MODE == "dbs" else storage_files


# =============================================================================
# WORKFLOWS
# =============================================================================
try:
    cfg = read_cfg(cfg_fpath, match=MATCH)
    print("cfg jsons:", list(cfg["jsons"].keys()))

    cat = Category(name="processing", cores=1, memory=1500, disk=4500)
    skim_cut = SKIM_CUT.replace(" ", "")

    wf = []
    for sample in sorted(cfg["jsons"]):
        jsn = cfg["jsons"][sample]
        print(f"Processing sample: {sample}")
        for fn in jsn["files"]:
            print(f"  {fn}")

        files = [x for x in jsn["files"]]
        module_name = pick_module(sample, DEFAULT_MODULE)

        if INPUT_MODE == "dbs":
            ds = cmssw.Dataset(
                dataset=jsn["path"],
                lumis_per_task=1,
                file_based=True,
            )
        else:
            ds = Dataset(
                files=files,
                files_per_task=1,
                patterns=["*.root"],
            )

        cmd = ["python3", WRAPPER]
        cmd += ["--cut", skim_cut]
        cmd += ["--module", module_name]
        cmd += ["--out-dir", "."]
        cmd += ["@inputfiles"]

        print("\nRemote command:\n", " ".join(cmd), "\n")

        skim_wf = Workflow(
            label=sample.replace("-", "_"),
            sandbox=cmssw.Sandbox(release=sandbox_location),
            dataset=ds,
            category=cat,
            extra_inputs=[WRAPPER],
            outputs=["output.root"],
            command=" ".join(cmd),
            merge_command="haddnano.py @outputfiles @inputfiles",
            merge_size="537M",
            globaltag=False,
            cleanup_input=False,
        )
        wf.append(skim_wf)
except Exception as e:
    print("Error while setting up workflows.")
    print("Please check your configuration and try again.")
    print("Error details:")
    print(e)
    wf = []
    raise Exception("Failed to set up workflows due to the above error.")


# =============================================================================
# ADVANCED OPTIONS (mode-dependent)
# =============================================================================
adv_kwargs = dict(
    bad_exit_codes=[127, 160],
    log_level=1,
    payload=10,
    osg_version="3.6",
    threshold_for_failure=10,
    threshold_for_skipping=10,
)

if INPUT_MODE == "dbs":
    adv_kwargs["xrootd_servers"] = [SRC_REMOTE]

config = Config(
    label=master_label,
    workdir=workdir_path,
    plotdir=plotdir_path,
    storage=storage,
    workflows=wf,
    advanced=AdvancedOptions(**adv_kwargs),
)
