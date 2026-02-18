import os
import subprocess

# Setup profile selection knob
ACTIVE_SETUP_PROFILE = "run2_el9_skims"

# Optional external markdown setup-profile file.
# If present and contains ACTIVE_SETUP_PROFILE, values from there are used.
SETUP_PROFILE_MARKDOWN_FILE = os.path.join(os.path.split(__file__)[0], "setup_profiles.md")

# Fallback setup profiles (used if markdown file is absent)
SETUP_PROFILES = {
    "run2_el9_skims": {
        "cmssw_release": "CMSSW_10_6_19_patch2",
        "scram_arch": "slc7_amd64_gcc700",
        "topeft_tag": "run3_test_mmerged",
        "topeft_url": "https://github.com/TopEFT/topeft.git",
        "cmgtools_url": "https://github.com/anpicci/topEFT_ttHMVA_Run3.git",
        "cmgtools_branch": "nd_run3",
        "nanoaodtools_url": "https://github.com/cms-nanoAOD/nanoAOD-tools.git",
        "nanoaodtools_branch": "",
    },
    "run3_mva_anpicci": {
        "cmssw_release": "CMSSW_14_0_6",
        "scram_arch": "el9_amd64_gcc12",
        "topeft_tag": "run3_test_mmerged",
        "topeft_url": "https://github.com/TopEFT/topeft.git",
        "cmgtools_url": "https://github.com/anpicci/topEFT_ttHMVA_Run3.git",
        "cmgtools_branch": "nd_run3",
        "nanoaodtools_url": "https://github.com/cms-nanoAOD/nanoAOD-tools.git",
        "nanoaodtools_branch": "",
    },
}


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


def main():
    top_dir, _ = os.path.split(__file__)
    if not top_dir:
        top_dir = "."

    os.chdir(top_dir)

    abs_path = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
    ).strip()

    md_profiles = parse_markdown_profiles(SETUP_PROFILE_MARKDOWN_FILE)
    if md_profiles:
        SETUP_PROFILES.update(md_profiles)

    if ACTIVE_SETUP_PROFILE not in SETUP_PROFILES:
        raise ValueError(
            f"Unknown ACTIVE_SETUP_PROFILE={ACTIVE_SETUP_PROFILE!r}. "
            f"Valid profiles: {', '.join(sorted(SETUP_PROFILES))}"
        )

    profile = SETUP_PROFILES[ACTIVE_SETUP_PROFILE]
    cmssw_release = profile["cmssw_release"]
    scram_arch = profile["scram_arch"]
    topeft_tag = profile["topeft_tag"]
    topeft_url = profile["topeft_url"]
    cmgtools_url = profile["cmgtools_url"]
    cmgtools_branch = profile["cmgtools_branch"]
    nanoaodtools_url = profile["nanoaodtools_url"]
    nanoaodtools_branch = profile["nanoaodtools_branch"]

    print(f"Selected ACTIVE_SETUP_PROFILE = {ACTIVE_SETUP_PROFILE}")
    print(f"Using setup profile markdown file: {SETUP_PROFILE_MARKDOWN_FILE}")

    if os.path.exists("topeft"):
        print("topeft directory already installed, skipping this part\n")
    else:
        print("Installing topeft cfg and json directories")
        prj_head = f"{abs_path}/topeft"
        cfg_dir = "input_samples/cfgs"
        json_dir = "input_samples/sample_jsons"
        subprocess.check_call(
            [
                f"{top_dir}/scripts/install_configs.sh",
                topeft_url,
                prj_head,
                topeft_tag,
                cfg_dir,
                json_dir,
            ]
        )
        print("")

    if os.path.exists(cmssw_release):
        print(f"CMSSW release {cmssw_release} detected, skipping this part")
    else:
        print("Setting up CMSSW release (NANOAODtools included)")
        subprocess.check_call(
            [
                "./scripts/install_cmssw.sh",
                abs_path,
                cmssw_release,
                scram_arch,
                cmgtools_url,
                cmgtools_branch,
                nanoaodtools_url,
                nanoaodtools_branch,
            ]
        )

    print("\nDone!\nMake sure not to run cmsenv when you are in your conda/mamba lobster env!")


main()
