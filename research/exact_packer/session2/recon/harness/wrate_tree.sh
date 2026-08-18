#!/bin/bash
# Build the rate-mode engine into a SIBLING TREE, so the queue in the main tree keeps running
# against the binary its earlier cells were taken with.
#
# The .so cannot simply be replaced in place.  OGC_WRATE unset is a no-op in the SOURCE, but not in
# the BINARY: this project has already measured a proved bit-identical speedup moving an objective
# 7.7%, and two dead calls behind switched-off flags moving prob_24 1.03%, because code layout
# changes timing and the beam derives its width from timing.  So an arm taken against a rebuilt .so
# is not comparable to one taken against the old one, and the A/B has to run base and arm against
# the SAME new binary -- which is what this tree is for.
set -u
R=/home/user/oraclemaster/research/exact_packer/session2/recon
cd "$R" || exit 1
D=build_wrate
mkdir -p $D
SFX=$(/usr/bin/python3.12-config --extension-suffix)
g++ -O3 -shared -std=c++17 -fPIC -fopenmp -w \
    $(/usr/bin/python3.12 -m pybind11 --includes) \
    ogc_fast.cpp -o "$D/ogc_fast$SFX" || { echo "BUILD FAILED"; exit 1; }
( cd $D || exit 1
  for f in myalgorithm.py bayrepack.py utils.py harness data ogc_state.py; do
      [ -e "$f" ] || [ ! -e "../$f" ] || ln -s "../$f" "$f"; done
  for f in "$R"/cranepack.cpython-*.so "$R"/ogc_geom.cpython-*.so; do
      [ -e "$f" ] && ln -sf "$f" .; done
  mkdir -p results/audit )
echo "built $D/ogc_fast$SFX  $(sha1sum $D/ogc_fast$SFX | cut -c1-12)"
