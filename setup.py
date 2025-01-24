import os
import subprocess



def main():
    top_dir,fname = os.path.split(__file__)
    if not top_dir:
        top_dir = "."

    os.chdir(top_dir)
    abs_path = subprocess.check_output(["git","rev-parse","--show-toplevel"])
    abs_path = abs_path.strip()

    cmssw_release = "CMSSW_14_0_6"
    scram_arch = "el9_amd64_gcc12"


    if os.path.exists("topeft"):
        print("topeft directory already installed, skipping this part\n")
    else:
        print("Installing topeft cfg and json directories")
        topeft_url = "https://github.com/TopEFT/topeft.git"
        tag = "master"
        prj_head = "{}/topeft".format(abs_path)
        cfg_dir  = "input_samples/cfgs"
        json_dir = "input_samples/sample_jsons"
        subprocess.check_call(["./scripts/install_configs.sh",topeft_url,prj_head,tag,cfg_dir,json_dir])
        print("")

    if os.path.exists(cmssw_release):
        print("CMSSW release {} detected, skipping this part".format(cmssw_release))
    else:
        print("Setting up CMSSW release and getting NanoAODTools")
        subprocess.check_call(["./scripts/install_cmssw.sh",abs_path,cmssw_release,scram_arch])

    print("\nDone!\nMake sure to do a cmsenv before activating and/or using lobster!")
main()
