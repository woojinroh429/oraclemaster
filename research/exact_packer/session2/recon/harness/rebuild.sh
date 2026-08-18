#!/bin/bash
# Rebuild ogc_fast with the double-move fix, and do not install it until it has been compared.
#
# The live .so is what every queue in results/ was measured with, and four ABI copies of it are
# what ships.  Overwriting them before the fix is checked would leave no way back and no baseline
# to check against -- so the new build goes to build_new/ and the current directory stays the old
# build.  run1.py resolves its import root from abspath(__file__), which does not follow symlinks,
# so a build_new/harness symlink makes build_new/ the import root and the two trees can be run
# against each other on the same instances at the same budget.
#
# WHAT THE COMPARISON IS FOR.  The fix changes what the beam carries.  The top-up pass used to
# re-move states the quota pass had taken, pushing hollow ones -- empty vectors, stale nplaced --
# into the next beam; now it takes states that were not taken yet.  So results are EXPECTED to
# move, and "identical" would mean the path never ran.  What has to hold is that nothing gets
# worse in a way the fix cannot explain, and that no run crashes or hangs.
#
# Only ogc_fast changed.  cranepack is linked in from the current tree rather than rebuilt, so a
# difference cannot come from it.
set -u
cd "$(dirname "$0")/.." || exit 1
R=$(pwd)
L=results/audit/rebuild.log
mkdir -p results/audit build_new; : > $L

echo "== build $(date -u +%H:%M:%S) ==" | tee -a $L
for v in 3.12 3.10 3.11 3.13; do
    sfx=$(python$v-config --extension-suffix 2>/dev/null) || { echo "no python$v" | tee -a $L; continue; }
    echo "-- python$v -> ogc_fast$sfx" | tee -a $L
    if ! g++ -O3 -shared -std=c++17 -fPIC -fopenmp $(python$v -m pybind11 --includes) \
         "$R/ogc_fast.cpp" -o "$R/build_new/ogc_fast$sfx" 2>>$L; then
        echo "BUILD FAILED for python$v -- nothing installed" | tee -a $L
        exit 1
    fi
done

# build_new/ as an import root: everything else comes from the current tree.
cd build_new || exit 1
for f in myalgorithm.py bayrepack.py utils.py harness data; do
    [ -e "$f" ] || ln -s "../$f" "$f"
done
for f in "$R"/cranepack.cpython-*.so; do ln -sf "$f" .; done
cd "$R" || exit 1

echo "== import check ==" | tee -a $L
( cd build_new && /usr/bin/python3.12 -c "
import ogc_fast, cranepack, os
print('ogc_fast  ', os.path.realpath(ogc_fast.__file__))
print('cranepack ', os.path.realpath(cranepack.__file__))" ) 2>&1 | tee -a $L

echo "== paired old vs new, same instances and budget ==" | tee -a $L
for p in 12 1 16 26 6 3; do
    echo "# P$p" >> $L
    timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 "[old.$p]" \
        --data data/stage2 >> $L 2>&1
    ( cd build_new && timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 "[new.$p]" \
        --data data/stage2 ) >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/rebuild.log \
      && git commit -q -m "in-flight: rebuild A/B P$p" ) >/dev/null 2>&1
done
echo "REBUILDDONE" >> $L
echo idle > harness/CURRENT
