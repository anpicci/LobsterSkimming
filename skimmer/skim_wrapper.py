import subprocess
import sys
import os

skim_cut = sys.argv[1]
output_dir = sys.argv[2]
infiles = sys.argv[3:]

if len(infiles) != 1:
    raise RuntimeError("The number of input files needs to be exactly 1")

fname = infiles[0]

subprocess.check_call(['nano_postproc.py','--cut={}'.format(skim_cut),output_dir,fname])

out_fn = fname.replace(".root","_Skim.root")

os.rename(out_fn,"output.root")

