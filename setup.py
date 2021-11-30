import os
import subprocess



def main():
    top_dir,fname = os.path.split(__file__)
    if not top_dir:
        top_dir = "."

    os.chdir(top_dir)
    abs_path = subprocess.check_output(["git","rev-parse","--show-toplevel"])
    abs_path = abs_path.strip()

    cmssw_release = "CMSSW_10_6_19_patch2"
    scram_arch = "slc7_amd64_gcc700"


    if os.path.exists("topcoffea"):
        print "topcoffea directory already installed, skipping this part\n"
    else:
        print "Installing topcoffea cfg and json directories"
        topcoffea_url = "https://github.com/TopEFT/topcoffea.git"
        tag = "master"
        prj_head = "{}/topcoffea".format(abs_path)
        cfg_dir  = "topcoffea/cfg"
        json_dir = "topcoffea/json"
        subprocess.check_call(["./scripts/install_configs.sh",topcoffea_url,prj_head,tag,cfg_dir,json_dir])
        print ""

    if os.path.exists(cmssw_release):
        print "CMSSW release {} detected, skipping this part".format(cmssw_release)
    else:
        print "Setting up CMSSW release and getting NanoAODTools"
        subprocess.check_call(["./scripts/install_cmssw.sh",abs_path,cmssw_release,scram_arch])

    print "\nDone!\nMake sure to do a cmsenv before activating and/or using lobster!"
main()
