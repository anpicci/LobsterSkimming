#!/bin/bash

# See: https://stackoverflow.com/questions/60190759/how-do-i-clone-fetch-or-sparse-checkout-a-single-directory-or-a-list-of-directo/60190760#60190760
# See Also: https://github.com/frgomes/bash-scripts/blob/master/bin/git_sparse_checkout
function git_sparse_checkout {
    local self=$(readlink -f "${BASH_SOURCE[0]}")
    local app=$(basename $self)
    local usage="USAGE: ${app} repository-URL [tag] [project-directory] [--] [list-of-paths]"

    # git repository, e.g.: http://github.com/frgomes/bash-scripts
    [[ $# != 0 ]] || (echo "${usage}" 1>&2 ; return 1)
    local arg=${1}
    [[ "${arg}" != "--" ]] || (echo "${usage}" 1>&2 ; return 1)
    local url="${arg}"
    [[ $# == 0 ]] || shift

    local prj=$(echo "$url" | sed 's:/:\n:g' | tail -1)

    if [[ "${arg}" != "--" ]] ;then arg="${1:-.}" ;fi
    if [[ "${arg}" == "--" || "${arg}" == "." ]] ;then
      local dir=$(readlink -f "./${prj}")
    else
      local dir=$(readlink -f "${arg}")
      [[ $# == 0 ]] || shift
    fi

    # default is master for historical reasons
    if [[ "${arg}" != "--" ]] ;then arg="${1:-master}" ;fi
    if [[ "${arg}" == "--" ]] ;then
      local tag=master
    else
      local tag="${arg}"
      [[ $# == 0 ]] || shift
    fi

    if [[ "${arg}" == "--" ]] ;then [[ $# == 0 ]] || shift; fi
    if [[ "${1:-}" == "--" ]] ;then [[ $# == 0 ]] || shift; fi

    # Note: any remaining arguments after these above are considered as a
    # list of files or directories to be downloaded.

    local sparse=true
    local opts='--depth=1'

    echo "url: ${url}"
    echo "dir: ${dir}"
    echo "tag: ${tag}"
    echo "prj: ${prj}"


    mkdir -p "${dir}"
    git -C "${dir}" init
    git -C "${dir}" config core.sparseCheckout ${sparse}
    for path in $* ;do
        echo "Getting ${path}"
        echo "${path}" >> ${dir}/.git/info/sparse-checkout
    done
    git -C "${dir}" remote add origin ${url}
    git -C "${dir}" fetch ${opts} origin ${tag}
    git -C "${dir}" checkout ${tag}
}

# Installs the topcoffea "cfg" and "json" directories
function install_topcoffea_configs {
    url=https://github.com/TopEFT/topcoffea.git
    tag=master
    prj_head=$(git rev-parse --show-toplevel)/topcoffea
    cfg_dir=topcoffea/cfg
    json_dir=topcoffea/json

    git_sparse_checkout ${url} ${prj_head} ${tag} -- ${cfg_dir} ${json_dir}
}


git_sparse_checkout $1 $2 $3 -- $4 $5
