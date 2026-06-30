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
YEAR = ""  # optional campaign filter; empty string keeps all valid Run 2 sample years
STEP = "skimmed"
TYPE = "background"  # used for labeling and output path; does not affect skim cut
# Select the cfg explicitly; YEAR is only an optional filter after cfg loading.
CFG_NAME = "mc_background_samples.cfg"
# CFG_NAME = "mc_signal_samples.cfg"
# CFG_NAME = "data_samples.cfg"
ALLOW_TYPE_CFG_MISMATCH = False

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

RUN2_YEARS = ("2016APV", "2016", "2017", "2018")


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


def normalize_campaign_type(type_value):
    normalized_type = str(type_value).strip().lower()
    allowed_types = {"data", "background", "signal"}
    if normalized_type not in allowed_types:
        raise ValueError(
            f"Invalid TYPE={type_value!r}; expected one of {sorted(allowed_types)}"
        )
    return normalized_type


def cfg_name_tokens(cfg_name):
    cfg_basename = os.path.basename(str(cfg_name)).lower()
    cfg_stem = os.path.splitext(cfg_basename)[0]
    return {
        token
        for token in re.split(r"[^a-z0-9]+", cfg_stem)
        if token
    }


def classify_cfg_name(cfg_name):
    tokens = cfg_name_tokens(cfg_name)
    matching_kinds = []

    if "data" in tokens:
        matching_kinds.append("data")
    if tokens.intersection({"background", "bkg"}):
        matching_kinds.append("background")
    if tokens.intersection({"signal", "sig"}):
        matching_kinds.append("signal")

    if len(matching_kinds) > 1:
        return "ambiguous"
    if not matching_kinds:
        return "unknown"
    return matching_kinds[0]


def validate_type_cfg_consistency(type_value, cfg_name, allow_mismatch=False):
    normalized_type = normalize_campaign_type(type_value)
    cfg_kind = classify_cfg_name(cfg_name)

    if cfg_kind == "unknown":
        raise ValueError(
            "Inconsistent Run 2 campaign identity: "
            f"TYPE={type_value!r} but CFG_NAME={cfg_name!r} has cfg kind {cfg_kind!r}. "
            "Refusing to derive TAG/workdir/plotdir/output paths. Use a cfg name "
            "containing a 'data', 'background', 'bkg', 'signal', or 'sig' token; "
            "ALLOW_TYPE_CFG_MISMATCH does not permit unknown cfg kinds."
        )

    if cfg_kind == "ambiguous":
        raise ValueError(
            "Inconsistent Run 2 campaign identity: "
            f"TYPE={type_value!r} but CFG_NAME={cfg_name!r} has cfg kind {cfg_kind!r} "
            "because more than one campaign marker was found. "
            "Refusing to derive TAG/workdir/plotdir/output paths. "
            "ALLOW_TYPE_CFG_MISMATCH does not permit ambiguous cfg kinds."
        )

    if cfg_kind != normalized_type and not allow_mismatch:
        raise ValueError(
            "Inconsistent Run 2 campaign identity: "
            f"TYPE={type_value!r} but CFG_NAME={cfg_name!r} has cfg kind {cfg_kind!r}. "
            "Refusing to derive TAG/workdir/plotdir/output paths. "
            f"Set TYPE to {cfg_kind!r}, choose a matching cfg, or explicitly set "
            "ALLOW_TYPE_CFG_MISMATCH=True."
        )

    return normalized_type, cfg_kind


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


def normalize_sample_year(value):
    if not isinstance(value, str):
        raise ValueError(f"sample year must be a string, got: {type(value).__name__}")

    text = value.strip()
    if not text:
        raise ValueError("sample year is missing or empty")

    upper = text.upper()
    if upper == "2016APV":
        return "2016APV"
    if text in ("2016", "2017", "2018"):
        return text

    raise ValueError(
        f"sample year {value!r} is not a supported Run 2 year; "
        f"expected one of {', '.join(RUN2_YEARS)}"
    )


def normalize_year_filter(year):
    if not isinstance(year, str):
        raise ValueError(f"YEAR must be a string, got: {type(year).__name__}")

    text = year.strip()
    if not text:
        return None
    if text.lower() == "multi-year":
        raise ValueError("YEAR='multi-year' is not supported; use YEAR='' for no year filter")

    try:
        return normalize_sample_year(text)
    except ValueError as err:
        raise ValueError(
            f"YEAR={year!r} is not a supported Run 2 campaign filter; "
            f"use '' or one of {', '.join(RUN2_YEARS)}"
        ) from err


def get_sample_year(sample, jsn, cfg_name):
    if "year" not in jsn:
        available_keys = ", ".join(sorted(str(key) for key in jsn.keys()))
        raise ValueError(
            f"Sample {sample!r} in cfg {cfg_name!r} is missing required JSON key 'year'; "
            f"available keys=[{available_keys}]"
        )

    try:
        return normalize_sample_year(jsn["year"])
    except ValueError as err:
        raise ValueError(
            f"Sample {sample!r} in cfg {cfg_name!r} has invalid JSON year {jsn.get('year')!r}: {err}"
        ) from err


def year_counts(sample_years_by_sample, samples=None):
    selected = samples if samples is not None else sample_years_by_sample
    counts = dict((year, 0) for year in RUN2_YEARS)
    for sample in selected:
        counts[sample_years_by_sample[sample]] += 1
    return counts


def print_year_counts(title, counts):
    print(title)
    for year in RUN2_YEARS:
        print(f"  {year}: {counts.get(year, 0)}")


def validate_campaign_year_filter(year_filter, sample_years_by_sample, cfg_name):
    if not sample_years_by_sample:
        raise ValueError(f"No active JSON samples were selected from cfg {cfg_name!r}")
    if year_filter is None:
        return
    if year_filter not in RUN2_YEARS:
        raise ValueError(
            f"Unsupported normalized year filter {year_filter!r}; expected one of {', '.join(RUN2_YEARS)}"
        )


def filter_cfg_jsons_by_year(cfg_jsons, year_filter, cfg_name):
    sample_years_by_sample = {
        sample: get_sample_year(sample, jsn, cfg_name)
        for sample, jsn in cfg_jsons.items()
    }
    validate_campaign_year_filter(year_filter, sample_years_by_sample, cfg_name)

    before_counts = year_counts(sample_years_by_sample)
    campaign_year_filter_label = year_filter if year_filter is not None else "all"
    print(f"Campaign year filter: {campaign_year_filter_label}")
    print_year_counts("Observed sample years before filtering:", before_counts)

    if year_filter is None:
        filtered_jsons = dict(cfg_jsons)
    else:
        filtered_jsons = {
            sample: jsn
            for sample, jsn in cfg_jsons.items()
            if sample_years_by_sample[sample] == year_filter
        }
        if not filtered_jsons:
            raise ValueError(
                f"YEAR={year_filter!r} removed every sample from cfg {cfg_name!r}; "
                "choose a year present in the selected cfg or use YEAR='' for no year filter"
            )

    filtered_years_by_sample = {
        sample: sample_years_by_sample[sample]
        for sample in filtered_jsons
    }
    print_year_counts(
        "Selected sample years after filtering:",
        year_counts(filtered_years_by_sample),
    )
    print(f"Selected samples after year filtering: {len(filtered_jsons)} of {len(cfg_jsons)}")
    return filtered_jsons, filtered_years_by_sample


def select_module_name(sample, sample_year):
    if sample_year == "2016APV":
        return "lepMVA_2016APV"
    if sample_year == "2017":
        return "lepMVA_2017"
    if sample_year == "2018":
        return "lepMVA_2018"
    if sample_year == "2016":
        return "lepMVA_2016"

    raise ValueError(f"Unsupported sample_year {sample_year!r} for sample {sample!r}")


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


def sample_input_mode_reason(input_mode, sample_input_mode):
    if sample_input_mode == "dbs":
        return "dbs_path"
    return "files_fallback"


# =============================================================================
# VALIDATION
# =============================================================================

INPUT_MODE = INPUT_MODE.strip().lower()
if INPUT_MODE not in ("dbs", "files", "auto"):
    raise ValueError(f"INPUT_MODE must be 'dbs', 'files', or 'auto', got: {INPUT_MODE!r}")

YEAR = YEAR.strip()
year_filter = normalize_year_filter(YEAR)

TARGET = TARGET.strip().upper()
if TARGET not in ("SR", "CR"):
    raise ValueError(f"TARGET must be 'SR' or 'CR', got: {TARGET!r}")

CAMPAIGN_TYPE, CFG_KIND = validate_type_cfg_consistency(
    TYPE,
    CFG_NAME,
    allow_mismatch=ALLOW_TYPE_CFG_MISMATCH,
)


# =============================================================================
# DERIVED PATHS / LABELS
# =============================================================================

TAG = f"{CAMPAIGN_TYPE}/NAOD_ULv9_lepMVA-run2"
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

print("Resolved Run 2 Lobster input configuration:")
print(f"  INPUT_MODE = {INPUT_MODE}")
print(f"  CFG_NAME = {CFG_NAME}")
print(f"  YEAR = {YEAR}")
print(f"  year_filter = {year_filter if year_filter is not None else 'all'}")
print(f"  TYPE = {TYPE}")
print(f"  cfg_kind = {CFG_KIND}")
print(f"  allow_type_cfg_mismatch = {ALLOW_TYPE_CFG_MISMATCH}")
print(f"  TARGET = {TARGET}")
print(f"  TAG = {TAG}")
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
    cfg_jsons, sample_years_by_sample = filter_cfg_jsons_by_year(
        cfg_jsons=cfg["jsons"],
        year_filter=year_filter,
        cfg_name=CFG_NAME,
    )
    print("selected cfg jsons:", list(sorted(cfg_jsons.keys())))

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

    for sample in sorted(cfg_jsons):
        jsn = cfg_jsons[sample]
        sample_year = sample_years_by_sample[sample]
        print(
            "Sample year decision: "
            f"sample={sample} sample_year={sample_year} "
            f"campaign_year_filter={year_filter if year_filter is not None else 'all'}"
        )
        sample_input_mode = decide_sample_input_mode(sample, jsn, INPUT_MODE)
        sample_reason = sample_input_mode_reason(INPUT_MODE, sample_input_mode)
        mode_counts[sample_input_mode] += 1

        print(f"Processing sample: {sample}")
        print(
            "Sample input mode decision: "
            f"sample={sample} input_mode={sample_input_mode} reason={sample_reason}"
        )
        print(f"  metadata summary: {metadata_summary(jsn)}")

        files = list(jsn["files"]) if sample_input_mode == "files" else []

        module_name = select_module_name(sample, sample_year)

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

print("Selected workflow input mode counts:")
print(f"  files: {mode_counts['files']}")
print(f"  dbs: {mode_counts['dbs']}")
print(f"Selected storage profile: {'files' if storage is storage_files else 'dbs'}")
print(f"xrootd_servers enabled: {str('xrootd_servers' in adv_kwargs).lower()}")


config = Config(
    label=master_label,
    workdir=workdir_path,
    plotdir=plotdir_path,
    storage=storage,
    workflows=workflows,
    advanced=AdvancedOptions(**adv_kwargs),
)
