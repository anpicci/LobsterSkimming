import subprocess
import sys
import os
import time
import argparse

parser = argparse.ArgumentParser(description='')
parser.add_argument('infiles', nargs='+', help='')
parser.add_argument('--cut','-c',type=str, help='')
parser.add_argument('--module','-m',type=str, help='')
parser.add_argument('--out-dir','-o',type=str,default='.', help='')

args = parser.parse_args()
skim_cut = args.cut
module   = args.module
out_dir  = args.out_dir
infiles  = args.infiles

if len(infiles) != 1:
    raise RuntimeError("The number of input files needs to be exactly 1")

fname = infiles[0]

cmd_args = ['nano_postproc.py']
cmd_args.extend(['-c','{}'.format(skim_cut)])
cmd_args.extend(['-I','CMGTools.TTHAnalysis.tools.nanoAOD.LepMVAULFriend',module])
cmd_args.extend([out_dir,fname])

print("Skim Command:"," ".join(cmd_args))
subprocess.check_call(cmd_args)

print("Sleeping...")
time.sleep(10)

out_fn = fname.rsplit("/")[-1]
out_fn = out_fn.replace(".root","_Skim.root")

print("Current working directory:")
for f in os.listdir('.'):
    print("\t{}".format(f))

print("Renaming {}".format(out_fn))
os.rename(out_fn,"output.root")

