#!/bin/bash
# CHECK OUT THE TWO SUBMITTED BUILDS AS THEY WERE SENT.
#
# The question is whether the third submission actually beat the second, and the only honest way
# to ask it is to run the two packages that were actually mailed -- not today's tree with knobs
# flipped.  Two of the four differences (salvage in the C++ beam, the ABI stamp) have no env
# switch at all, so an env-based reconstruction of the second submission is not the second
# submission.
#
# Both trees carry their own prebuilt cpython-312 .so files, which is what the grader would have
# loaded, so nothing is compiled here.  Note that BOTH still contain the double-move segfault
# found on 08-06 -- that is deliberate, it is what was submitted, and the runner bounds the wait.
#
# builds/ is untracked on purpose: it is 12 MB of binaries already in git history, and this
# script regenerates it in a second after the container wipes untracked files again.
#
#   sub2  d6d2a78  08-04 04:57  the package the second submission was made from
#   sub3  62c423d  08-05 10:12  the package the third submission was made from
set -eu
cd "$(dirname "$0")/.."
ROOT="$(git rev-parse --show-toplevel)"
REL="research/exact_packer/session2/recon/submission"
mk(){ # name sha
    rm -rf "builds/$1"; mkdir -p "builds/$1"
    ( cd "$ROOT" && git archive "$2" "$REL" ) | tar -x -C "builds/$1" --strip-components=5
    echo "$2" > "builds/$1/SHA"
    echo "builds/$1  $2  $(ls builds/$1 | wc -l) files"
}
mkdir -p builds
mk sub2 d6d2a78
mk sub3 62c423d
