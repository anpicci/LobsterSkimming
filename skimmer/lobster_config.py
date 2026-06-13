import datetime
import os
import re
import shlex
import subprocess
import sys

from lobster import cmssw
from lobster.core import AdvancedOptions, Category, Config, Dataset, StorageConfiguration, Workflow

sys.path.append(os.path.split(__file__)[0])
from tools.utils import read_cfg


# =============================================================================
# USER KNOBS
# =============================================================================

TESTING = False

# Choose one:
#   "dbs"   -> cmssw.Dataset(dataset=..., file_based=True) + advanced.xrootd_servers
#   "files" -> Dataset(files=...) + StorageConfiguration(input=[root://...//])
#   "auto"  -> per-sample choice: DBS-style path when available, files otherwise
INPUT_MODE = "auto"

# Choose one protocol:
#   "root://"  # used for remote XRootD paths
#   "file://"  # used for local CephFS paths
PROTOCOL_LOCAL = "file://"
PROTOCOL_REMOTE = "root://"

TARGET = "CR"  # impacts the inclusion of the two-lepton veto in the skim cut
YEAR = "2016APV"  # used for labeling and module selection; does not affect input dataset selection
STEP = "skimmed"
TYPE = "background"
TAG = f"{TYPE}/NAOD_ULv9_lepMVA-run2/{YEAR}"
# CFG_NAME = f"ND_{YEAR}_{TYPE}_samples.cfg" if TYPE != "data" else f"{YEAR}_data.cfg"
CFG_NAME = "mc_background_samples.cfg"


# Empty list matches everything.
# For first retry, strongly consider something like:
# MATCH = [r".*ZG.*PTG_200to400.*\.json"]
MATCH = []

WRAPPER = "skim_wrapper.py"

# XRootD endpoints
SRC_REMOTE = "cms-xrd-global.cern.ch"
SRC_LOCAL = "/cms/cephfs/data"

DST_REMOTE = "cmsxrootd.crc.nd.edu"
DST_LOCAL = "/cms/cephfs/data"

WORKDIR_BASE = "/tmpscratch/users/$USER"


# =============================================================================
# HELPERS
# =============================================================================

DBS_DATA_TIERS = {
    "NANOAOD",
    "NANOAODSIM",
    "MINIAOD",
    "MINIAODSIM",
    "AOD",
    "AODSIM",
    "USER",
}


def remove_whitespace(expr):
    return re.sub(r"\s+", "", expr)


def assert_balanced_parentheses(expr, label):
    depth = 0

    for idx, char in enumerate(expr):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1

        if depth < 0:
            raise ValueError(
                f"{label} has an unmatched closing parenthesis at position {idx}: {expr}"
            )

    if depth != 0:
        raise ValueError(
            f"{label} has unbalanced parentheses with final depth {depth}: {expr}"
        )


def assert_no_literal_outer_quotes(expr, label):
    if len(expr) >= 2 and expr[0] == expr[-1] and expr[0] in ("'", '"'):
        raise ValueError(
            f"{label} starts and ends with literal quote characters. "
            f"Do not include shell quotes in the Lobster argument value: {expr!r}"
        )


def build_skim_cut(target):
    # Keep each per-object requirement wrapped in one explicit outer pair of parentheses.
    # This makes Sum$({req}) and charge-weighted Sum$ expressions unambiguous.
    el_req = (
        "(Electron_pt>10"
        " && Electron_miniPFRelIso_all<0.4"
        " && Electron_sip3d<8"
        " && (abs(Electron_eta + Electron_deltaEtaSC)<1.4442"
        " || abs(Electron_eta + Electron_deltaEtaSC)>1.566))"
    )

    mu_req = (
        "(Muon_pt>10"
        " && Muon_looseId"
        " && Muon_miniPFRelIso_all<0.4"
        " && Muon_sip3d<8)"
    )

    ta_req = (
        "(Tau_pt>20"
        " && abs(Tau_dxy)<0.05"
        " && abs(Tau_dz)<1"
        " && Tau_idDeepTau2017v2p1VSe>1"
        " && Tau_idDeepTau2017v2p1VSmu>0"
        " && Tau_idDeepTau2017v2p1VSjet>1)"
    )

    for label, expr in [
        ("el_req", el_req),
        ("mu_req", mu_req),
        ("ta_req", ta_req),
    ]:
        assert_balanced_parentheses(expr, label)

    num_leps = f"(Sum$({el_req}) + Sum$({mu_req}) + Sum$({ta_req}))"
    net_charge = (
        f"(Sum$(Electron_charge*{el_req})"
        f" + Sum$(Muon_charge*{mu_req})"
        f" + Sum$(Tau_charge*{ta_req}))"
    )

    os2l_veto = f"(({num_leps} != 2) || ({net_charge} != 0))"
    nlep_req = f"({num_leps} >= 2)"

    if target == "SR":
        skim_cut = f"{nlep_req} && {os2l_veto}"
    else:
        skim_cut = nlep_req

    skim_cut = remove_whitespace(skim_cut)

    for label, expr in [
        ("num_leps", remove_whitespace(num_leps)),
        ("net_charge", remove_whitespace(net_charge)),
        ("os2l_veto", remove_whitespace(os2l_veto)),
        ("nlep_req", remove_whitespace(nlep_req)),
        ("skim_cut", skim_cut),
    ]:
        assert_balanced_parentheses(expr, label)
        assert_no_literal_outer_quotes(expr, label)

    return skim_cut


def select_module_name(sample):
    if "HIPM_UL2016" in sample or "16APV" in sample:
        return "lepMVA_2016APV"
    if "UL2017" in sample or "UL17" in sample:
        return "lepMVA_2017"
    if "UL2018" in sample or "UL18" in sample:
        return "lepMVA_2018"
    if "2022" in sample or "2023" in sample:
        return "lepMVA"

    return "lepMVA_2016"


def build_payload_command(wrapper, skim_cut, module_name, out_dir):
    # cmd = ["python3", wrapper]
    cmd = ["python", wrapper]
    cmd += ["--cut", skim_cut]
    cmd += ["--module", module_name]
    cmd += ["--out-dir", out_dir]
    cmd += ["@inputfiles"]

    # Important:
    # - command_string is the actual string passed to Lobster.
    # - display_command is only for human logs/copy-paste.
    # Do not use shlex.join as the actual Lobster command unless Lobster's parser is
    # confirmed to handle shell quoting exactly as expected.
    command_string = " ".join(cmd)
    display_command = shlex.join(cmd)

    return command_string, display_command


def is_dbs_dataset_path(value):
    if not isinstance(value, str):
        return False

    value = value.strip()
    if not value.startswith("/"):
        return False
    if value.startswith("/store/") or value == "/store":
        return False
    if value.startswith("root://") or value.startswith("file://"):
        return False

    parts = [part for part in value.split("/") if part]
    if len(parts) != 3:
        return False

    return parts[-1] in DBS_DATA_TIERS


def has_usable_files(jsn):
    files = jsn.get("files")
    return (
        isinstance(files, list)
        and len(files) > 0
        and all(isinstance(fn, str) and bool(fn.strip()) for fn in files)
    )


def get_path_kind(value):
    if not isinstance(value, str) or not value.strip():
        return "missing_or_empty"
    value = value.strip()
    if is_dbs_dataset_path(value):
        return "dbs_dataset"
    if value.startswith("/store/") or value == "/store":
        return "storage_path"
    if value.startswith("root://"):
        return "root_url"
    if value.startswith("file://"):
        return "file_url"
    if value.startswith("/"):
        return "absolute_non_dbs_path"
    return "other"


def metadata_summary(jsn):
    files = jsn.get("files")
    files_count = len(files) if isinstance(files, list) else 0
    path = jsn.get("path")
    return (
        f"path_kind={get_path_kind(path)}, "
        f"has_path={'path' in jsn}, "
        f"files_count={files_count}, "
        f"has_usable_files={has_usable_files(jsn)}"
    )


def sample_contract_error(sample, input_mode, sample_input_mode, required_key, jsn, detail):
    available_keys = ", ".join(sorted(str(key) for key in jsn.keys()))
    return ValueError(
        f"Invalid sample metadata for sample {sample!r}: {detail}. "
        f"global INPUT_MODE={input_mode!r}; "
        f"sample input mode={sample_input_mode!r}; "
        f"required key={required_key!r}; "
        f"available keys=[{available_keys}]; "
        f"source metadata summary: {metadata_summary(jsn)}"
    )


def validate_files_contract(sample, jsn, input_mode, sample_input_mode="files"):
    if has_usable_files(jsn):
        return

    raise sample_contract_error(
        sample=sample,
        input_mode=input_mode,
        sample_input_mode=sample_input_mode,
        required_key="files",
        jsn=jsn,
        detail="expected a nonempty 'files' list of nonempty strings",
    )


def validate_dbs_contract(sample, jsn, input_mode, sample_input_mode="dbs"):
    if is_dbs_dataset_path(jsn.get("path")):
        return

    raise sample_contract_error(
        sample=sample,
        input_mode=input_mode,
        sample_input_mode=sample_input_mode,
        required_key="path",
        jsn=jsn,
        detail=(
            "expected 'path' to use /PrimaryDataset/ProcessedDataset/DataTier "
            "DBS syntax; /store/... paths are not DBS dataset names"
        ),
    )


def decide_sample_input_mode(sample, jsn, input_mode):
    if input_mode == "files":
        validate_files_contract(sample, jsn, input_mode, sample_input_mode="files")
        return "files"

    if input_mode == "dbs":
        validate_dbs_contract(sample, jsn, input_mode, sample_input_mode="dbs")
        return "dbs"

    if input_mode == "auto":
        if is_dbs_dataset_path(jsn.get("path")):
            return "dbs"
        if has_usable_files(jsn):
            return "files"
        raise sample_contract_error(
            sample=sample,
            input_mode=input_mode,
            sample_input_mode="auto",
            required_key="path or files",
            jsn=jsn,
            detail=(
                "auto mode requires either a DBS-style 'path' or a usable "
                "nonempty 'files' list"
            ),
        )

    raise ValueError(f"INPUT_MODE must be 'dbs', 'files', or 'auto', got: {input_mode!r}")


# =============================================================================
# VALIDATION
# =============================================================================

INPUT_MODE = INPUT_MODE.strip().lower()
if INPUT_MODE not in ("dbs", "files", "auto"):
    raise ValueError(f"INPUT_MODE must be 'dbs', 'files', or 'auto', got: {INPUT_MODE!r}")

TARGET = TARGET.strip().upper()
if TARGET not in ("SR", "CR"):
    raise ValueError(f"TARGET must be 'SR' or 'CR', got: {TARGET!r}")


# =============================================================================
# DERIVED PATHS / LABELS
# =============================================================================

TSTAMP1 = datetime.datetime.now().strftime("%Y%m%d_%H%M")
startingday = datetime.datetime.now().strftime("%y%m%d")
ver = f"v{startingday}"

try:
    top_dir = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"]
    ).decode("utf-8").strip()

    # sandbox_location = os.path.join(top_dir, "CMSSW_14_0_6")
    sandbox_location = os.path.join(top_dir, "CMSSW_10_6_19_patch2")
    print(f"Sandbox location: {sandbox_location}")

    cfg_fpath = os.path.join(top_dir, "topeft", "input_samples", "cfgs", CFG_NAME)
    print(f"Where is your cfg?\t {cfg_fpath}")

except Exception as err:
    print(
        "Error while determining top-level directory or cfg file path. "
        "Please check your git repository and configuration. Error details:"
    )
    print(err)
    raise RuntimeError("Failed to set up configuration due to the above error.") from err


mode_stamp = INPUT_MODE
master_label = f"{STEP}_{TARGET}_{mode_stamp}_lobPY3_{TSTAMP1}"
workdir_path = f"{WORKDIR_BASE}/{STEP}_{TARGET}/{TAG}/{ver}"
plotdir_path = f"~/www/lobster/{STEP}_{TARGET}/{TAG}/{ver}"
output_path = f"/store/user/$USER/{STEP}_{TARGET}/{TAG}/{ver}"

if TESTING:
    master_label = f"{STEP}_{TARGET}_{mode_stamp}_testlobPY3_{TSTAMP1}"
    workdir_path = f"{WORKDIR_BASE}/{STEP}_{TARGET}/test/lobster_skimtest_{TSTAMP1}"
    plotdir_path = f"~/www/lobster/{STEP}_{TARGET}/test/lobster_skimtest_{TSTAMP1}"
    output_path = f"/store/user/$USER/{STEP}_{TARGET}/test/lobster_skimtest_{TSTAMP1}"


# =============================================================================
# STORAGE
# =============================================================================

SRC_PREFIX_LOCAL = PROTOCOL_LOCAL + SRC_LOCAL + "//"
DST_PREFIX_LOCAL = PROTOCOL_LOCAL + DST_LOCAL + "//"

SRC_PREFIX_REMOTE = PROTOCOL_REMOTE + SRC_REMOTE + "//"
DST_PREFIX_REMOTE = PROTOCOL_REMOTE + DST_REMOTE + "//"

storage_dbs = StorageConfiguration(
    output=[
        f"{DST_PREFIX_REMOTE}{output_path}",
    ],
    disable_input_streaming=False,
)

storage_files = StorageConfiguration(
    input=[
        SRC_PREFIX_LOCAL,
        SRC_PREFIX_REMOTE,
    ],
    output=[
        f"{DST_PREFIX_LOCAL}{output_path}",
        f"{DST_PREFIX_REMOTE}{output_path}",
    ],
    disable_input_streaming=False,
)

# =============================================================================
# SKIM CUT
# =============================================================================

skim_cut = build_skim_cut(TARGET)

print(f"INPUT_MODE = {INPUT_MODE}")
print(f"TARGET = {TARGET}")
print(f"SRC_PREFIX_LOCAL = {SRC_PREFIX_LOCAL}")
print(f"SRC_PREFIX_REMOTE = {SRC_PREFIX_REMOTE}")
print(f"DST_PREFIX_LOCAL = {DST_PREFIX_LOCAL}")
print(f"DST_PREFIX_REMOTE = {DST_PREFIX_REMOTE}")
print(f"Local output path:  {DST_PREFIX_LOCAL}{output_path}")
print(f"Remote output path: {DST_PREFIX_REMOTE}{output_path}")
print(f"skim_cut repr: {skim_cut!r}")
print(f"skim_cut: {skim_cut}")

assert_no_literal_outer_quotes(skim_cut, "skim_cut")
assert_balanced_parentheses(skim_cut, "skim_cut")


# =============================================================================
# WORKFLOWS
# =============================================================================

try:
    cfg = read_cfg(cfg_fpath, match=MATCH)
    print("cfg jsons:", list(cfg["jsons"].keys()))

    cat = Category(
        name="processing",
        cores=1,
        memory=1500,
        disk=4500,
    )

    workflows = []
    mode_counts = {
        "files": 0,
        "dbs": 0,
    }

    for sample in sorted(cfg["jsons"]):
        jsn = cfg["jsons"][sample]
        sample_input_mode = decide_sample_input_mode(sample, jsn, INPUT_MODE)
        mode_counts[sample_input_mode] += 1

        print(f"Processing sample: {sample}")
        print(f"  selected input mode: {sample_input_mode}")
        print(f"  metadata summary: {metadata_summary(jsn)}")

        files = list(jsn["files"]) if sample_input_mode == "files" else []

        if sample_input_mode == "files":
            for fn in files:
                print(f"  {fn}")

        module_name = select_module_name(sample)

        if sample_input_mode == "dbs":
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

        command_string, display_command = build_payload_command(
            wrapper=WRAPPER,
            skim_cut=skim_cut,
            module_name=module_name,
            out_dir=".",
        )

        print("\nActual Lobster command string:")
        print(command_string)

        print("\nCopy-paste-safe display command:")
        print(display_command)

        skim_wf = Workflow(
            label=sample.replace("-", "_"),
            sandbox=cmssw.Sandbox(release=sandbox_location),
            dataset=ds,
            category=cat,
            extra_inputs=[WRAPPER, os.path.join(sandbox_location,'src/PhysicsTools/NanoAODTools/scripts/haddnano.py')],
            outputs=["output.root"],
            command=command_string,
            merge_command="haddnano.py @outputfiles @inputfiles",
            merge_size="537M",
            globaltag=False,
            cleanup_input=False,
        )

        workflows.append(skim_wf)

    print("Selected workflow input mode counts:")
    print(f"  files: {mode_counts['files']}")
    print(f"  dbs: {mode_counts['dbs']}")

except Exception as err:
    print(
        "Error while setting up workflows. "
        "Please check your configuration and try again. Error details:"
    )
    print(err)
    raise RuntimeError("Failed to set up workflows due to the above error.") from err


# =============================================================================
# FINAL STORAGE SELECTION
# =============================================================================

if INPUT_MODE == "files":
    storage = storage_files
elif INPUT_MODE == "dbs":
    storage = storage_dbs
elif INPUT_MODE == "auto":
    storage = storage_files if mode_counts["files"] else storage_dbs
else:
    raise ValueError(f"INPUT_MODE must be 'dbs', 'files', or 'auto', got: {INPUT_MODE!r}")

print(f"Selected storage profile: {'files' if storage is storage_files else 'dbs'}")


# =============================================================================
# ADVANCED OPTIONS
# =============================================================================

adv_kwargs = dict(
    bad_exit_codes=[127, 160],
    log_level=1,
    payload=10,
    osg_version="3.6",
    threshold_for_failure=10,
    threshold_for_skipping=10,
)

if mode_counts["dbs"]:
    adv_kwargs["xrootd_servers"] = [SRC_REMOTE]


config = Config(
    label=master_label,
    workdir=workdir_path,
    plotdir=plotdir_path,
    storage=storage,
    workflows=workflows,
    advanced=AdvancedOptions(**adv_kwargs),
)
