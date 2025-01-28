#!/bin/bash

# Usage: ./install_cmssw.sh install-dir cmssw-version

function setup_cmssw {
    dir=$1
    cmssw_ver=$2

    cd ${dir}

    if [[ "${CMSSW_BASE}" != "" ]]; then
        echo "Already in a CMSSW release! Must start from a fresh environment, exiting now"
        return 1
    fi

    cvmfs_dir=/cvmfs/cms.cern.ch

    echo "dir: ${dir}"
    echo "cmssw_release: ${cmssw_ver}"

    if [ -d ${cvmfs_dir} ]; then
        echo "Found CVMFS!"
        # Makes cmsrel available to the environment
        source ${cvmfs_dir}/cmsset_default.sh
    else
        echo "Couldn't find CVMFS directory, exiting now"
        return 1
    fi

    export SCRAM_ARCH=$3

    echo "Setting up ${cmssw_ver}"
    scram p CMSSW ${cmssw_ver}

    cd ${cmssw_ver}/src
    #git clone git@github.com:sscruz/cmgtools-lite.git -b 104X_dev_nano_lepMVA CMGTools
    #git clone https://github.com/jdelrieg/topEFT_ttHMVA_Run3.git -b newcmgtools_python3 CMGTools
    git clone https://github.com/apiccine/topEFT_ttHMVA_Run3.git -b nd_run3 CMGTools
    #git clone https://github.com/cms-nanoAOD/nanoAOD-tools.git PhysicsTools/NanoAODTools
    echo "Getting CMS ENV from ${PWD}"
    eval $(scramv1 runtime -sh)
    scram b
}

setup_cmssw $1 $2 $3
