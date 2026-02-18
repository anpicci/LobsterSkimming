#!/usr/bin/env bash
# Usage:
# ./install_cmssw.sh <install-dir> <cmssw-version> <scram-arch> <cmgtools-url> <cmgtools-branch> <nanoaodtools-url> <nanoaodtools-branch>

set -euo pipefail

setup_cmssw() {
    local dir="$1"
    local cmssw_ver="$2"
    local scram_arch="$3"
    local cmgtools_url="$4"
    local cmgtools_branch="$5"
    local nanoaodtools_url="$6"
    local nanoaodtools_branch="$7"

    cd "${dir}" || { echo "ERROR: directory '${dir}' does not exist"; return 1; }

    if [[ -n "${CMSSW_BASE:-}" ]]; then
        echo "Already in a CMSSW release (${CMSSW_BASE})!"
        echo "Must start from a fresh environment, exiting now."
        return 1
    fi

    local cvmfs_dir=/cvmfs/cms.cern.ch

    echo "dir: ${dir}"
    echo "cmssw_release: ${cmssw_ver}"
    echo "SCRAM_ARCH: ${scram_arch}"
    echo "CMGTools source: ${cmgtools_url} (${cmgtools_branch:-default branch})"
    echo "NanoAODTools source: ${nanoaodtools_url} (${nanoaodtools_branch:-default branch})"

    if [[ -d "${cvmfs_dir}" ]]; then
        echo "Found CVMFS!"
        # shellcheck source=/dev/null
        source "${cvmfs_dir}/cmsset_default.sh"
    else
        echo "Couldn't find CVMFS directory (${cvmfs_dir}), exiting now"
        return 1
    fi

    export SCRAM_ARCH="${scram_arch}"

    echo "Setting up ${cmssw_ver}"
    scram p CMSSW "${cmssw_ver}"

    cd "${cmssw_ver}/src"

    if [[ -n "${cmgtools_branch}" ]]; then
        git clone "${cmgtools_url}" -b "${cmgtools_branch}" CMGTools
    else
        git clone "${cmgtools_url}" CMGTools
    fi

    mkdir -p PhysicsTools
    if [[ -n "${nanoaodtools_branch}" ]]; then
        git clone "${nanoaodtools_url}" -b "${nanoaodtools_branch}" PhysicsTools/NanoAODTools
    else
        git clone "${nanoaodtools_url}" PhysicsTools/NanoAODTools
    fi

    echo "Getting CMS ENV from ${PWD}"
    eval "$(scramv1 runtime -sh)"
    scram b
}

setup_cmssw "$@"
