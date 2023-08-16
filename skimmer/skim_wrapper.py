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

indent = " "*4*2

s = ["Current working directory:"]
for f in os.listdir('.'):
    s.append(indent + "{}".format(f))
print "\n".join(s)

# This is going to be our last resort...
local_files = []
for inf in infiles:
    #local_name = inf.rsplit("/")[-1]
    local_name = inf.rsplit("/")[-1].replace("file:","")
    local_files.append(local_name)
    if local_name.replace("file:","") in os.listdir('.'):
        continue
    elif local_name in os.listdir('.'):
        continue
    cmd_args = ['xrdcp','-f',inf,local_name]
    s = "Copy command: {}".format(" ".join(cmd_args))
    print s
    subprocess.check_call(cmd_args)

s = "Sleeping..."
print s
time.sleep(10)

to_skim = local_files

cmd_args = ['nano_postproc.py']
cmd_args.extend(['-c','{}'.format(skim_cut)])
cmd_args.extend(['-I','CMGTools.TTHAnalysis.tools.nanoAOD.ttH_modules','lepJetBTagDeepFlav,{}'.format(module)])
cmd_args.extend([out_dir])
cmd_args.extend(to_skim)

s = "Skim command: {}".format(" ".join(cmd_args))
print s
subprocess.check_call(cmd_args)

s = "Sleeping..."
print s
time.sleep(10)
 
s = ["Current working directory:"]
print s
for f in os.listdir('.'):
    s.append(indent + "{}".format(f))
print "\n".join(s)

# Need to merge any skim outputs into a single file that lobster expects
to_merge = [ x.rsplit("/")[-1].replace(".root","_Skim.root") for x in to_skim ]

cmd_args = ['python','haddnano.py','output.root']
cmd_args.extend(to_merge)
s = "Merge command: {}".format(" ".join(cmd_args))
print s
subprocess.check_call(cmd_args)

