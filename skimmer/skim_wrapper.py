import subprocess
import sys
import os

skim_cut = sys.argv[1]
output_dir = sys.argv[2]
infiles = sys.argv[3:]

if len(infiles) != 1:
    raise RuntimeError("The number of input files needs to be exactly 1")

fname = infiles[0]

cmd_args = ['nano_postproc.py','-c','{}'.format(skim_cut),output_dir,fname]
print("Skim Command:"," ".join(cmd_args))
subprocess.check_call(cmd_args)

out_fn = fname.replace(".root","_Skim.root")

os.rename(out_fn,"output.root")

