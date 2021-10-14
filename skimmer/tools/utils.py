import re
import os
import json

pjoin = os.path.join

# Match strings using one or more regular expressions
def regex_match(lst,regex_lst):
    # NOTE: For the regex_lst patterns, we use the raw string to generate the regular expression.
    #       This means that any regex special characters in the regex_lst should be properly
    #       escaped prior to calling this function.
    # NOTE: The input list is assumed to be a list of str objects and nothing else!
    matches = []
    if len(regex_lst) == 0: return lst[:]
    for s in lst:
        for pat in regex_lst:
            m = re.search(r"{}".format(pat),s)
            if m is not None:
                matches.append(s)
                break
    return matches

def load_json_file(fpath):
    if not os.path.exists(fpath):
        raise RuntimeError("fpath '{fpath}' does not exist!".format(fpath=fpath))
    with open(fpath) as f:
        jsn = json.load(f)
    for i,fn in enumerate(jsn['files']):
        fn = fn.replace("//","/")
        jsn['files'][i] = fn
    return jsn

def read_cfg(fpath):
    cfg_dir,fname = os.path.split(fpath)
    if not cfg_dir:
        raise RuntimeError("No cfg directory in {fpath}".format(fpath=fpath))
    if not os.path.exists(cfg_dir):
        raise RuntimeError("{cfg_dir} does not exist!".format(cfg_dir=cfg_dir))
    cfg = {
        "cfg_dir": cfg_dir,
        "src_xrd": "",
        "dst_xrd": "",
        "jsons": {},
    }
    with open(fpath) as f:
        for l in f:
            l = l.strip().split("#")[0]
            if not len(l): continue
            if l.startswith("root:"):
                cfg['src_xrd'] = l
            else:
                sample = os.path.basename(l)
                sample = sample.replace(".json","")
                full_path = pjoin(cfg['cfg_dir'],l)
                jsn = load_json_file(full_path)
                cfg['jsons'][sample] = jsn
    return cfg