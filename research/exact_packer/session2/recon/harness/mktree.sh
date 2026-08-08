#!/bin/bash
# mktree.sh <dir>  -- build the current ogc_fast.cpp into a sibling tree, so an A/B runs both arms
# against the SAME fresh binary while the main tree's queue keeps its own.
#
# Unset env is a no-op in the SOURCE and not in the BINARY: this project has measured a proved
# bit-identical speedup move an objective 7.7%, because code layout changes timing and the beam
# derives its width from timing.  Comparing a new .so against the tree's shipped one confounds the
# patch with the rebuild.
set -u
R=/home/user/oraclemaster/research/exact_packer/session2/recon
D="${1:?usage: mktree.sh <dir>}"
cd "$R" || exit 1
mkdir -p "$D"
SFX=$(/usr/bin/python3.12-config --extension-suffix)
g++ -O3 -shared -std=c++17 -fPIC -fopenmp -w \
    $(/usr/bin/python3.12 -m pybind11 --includes) \
    ogc_fast.cpp -o "$D/ogc_fast$SFX" || { echo "BUILD FAILED"; exit 1; }
( cd "$D" || exit 1
  for f in myalgorithm.py bayrepack.py utils.py harness data ogc_state.py; do
      [ -e "$f" ] || [ ! -e "../$f" ] || ln -s "../$f" "$f"; done
  for f in "$R"/cranepack.cpython-*.so "$R"/ogc_geom.cpython-*.so; do
      [ -e "$f" ] && ln -sf "$f" .; done
  mkdir -p results/audit )
echo "built $D/ogc_fast$SFX  $(sha1sum "$D/ogc_fast$SFX" | cut -c1-12)"
