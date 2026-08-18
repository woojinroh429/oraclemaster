#!/bin/bash
# Rebuild the submission package from the TREE, then prove the zip is what the tree says.
#
# Two failures this package has already had, both silent:
#   - the zip's myalgorithm.py was stale against the tree, so a fix that was measured all night
#     was not the code that got submitted;
#   - only the cpython-312 .so shipped, and when the container came back on 3.11 the extensions
#     stopped importing, myalgorithm caught the ImportError and returned a legal PYTHON-FALLBACK
#     answer -- prob_36 scored 4,023,023,953 against 87,632,418, feasible, no warning anywhere.
#
# So: copy from the tree, byte-compare every entry afterwards, ship all four ABI tags, and run
# the result in an empty directory with PYTHONPATH stripped, asserting the extensions resolve to
# THAT directory and not to the source tree.
set -e
cd "$(dirname "$0")/.."

# A third silent failure, caught before it shipped: ogc_fast.cpp gained the beam's salvage and the
# OGC_BEAMAIM knob, only the 3.12 binary was rebuilt, and the 3.10/3.11/3.13 files sat two days
# stale in the tree.  Packaging copies from the tree, so all three would have gone out -- and on
# any grader that is not 3.12 the portfolio axis validated at 31-6 would simply not exist.  Every
# .so now carries the hash of the source it was built from; refuse to package a set that disagrees.
echo "== 확장 모듈이 지금 소스에서 나온 것인지 =="
for m in ogc_fast cranepack; do
  SHA=$(sha1sum "$m.cpp" | cut -c1-12)
  n=0
  for f in $m.cpython-3*.so; do
    n=$((n+1))
    if grep -qa "OGCSRC=$SHA" "$f"; then echo "  OK    $f  $SHA"
    else echo "  STALE $f  (소스는 $SHA)"; STALE=1; fi
  done
  [ $n -ge 4 ] || { echo "  ABI $n 개뿐 -- 4개 필요"; STALE=1; }
done
[ -z "${STALE:-}" ] || { echo "빌드 중단: bash harness/buildabi.sh 를 먼저 돌리십시오"; exit 1; }

S=submission
rm -rf $S && mkdir -p $S
cp myalgorithm.py bayrepack.py utils.py cranepack.cpp ogc_fast.cpp $S/
cp cranepack.cpython-3*.so ogc_fast.cpython-3*.so $S/
cat > $S/build.txt <<'TXT'
BUILD INSTRUCTIONS
==================

The .so files in this zip are ALREADY COMPILED and no build step is required to run the
algorithm.  The rules state that server-side compilation is not performed.

WHY FOUR COPIES OF EACH EXTENSION.  A CPython extension carries the interpreter's ABI tag in its
filename, so ogc_fast.cpython-312-....so is invisible to Python 3.11.  myalgorithm catches the
ImportError and falls back to a pure-Python path that still returns a legal solution -- roughly
45x worse, with no error anywhere.  Shipping 3.10 / 3.11 / 3.12 / 3.13 removes that failure mode
whatever the evaluation image turns out to be; the four files coexist and Python picks its own.

CONTENTS
--------
    myalgorithm.py    entry point.  algorithm(prob_info, timelimit) -> solution dict
    bayrepack.py      the exact bay-repacking operator (pure Python; calls cranepack)
    utils.py          unmodified copy of the provided module
    ogc_fast.cpython-3{10,11,12,13}-x86_64-linux-gnu.so    construction engine
    cranepack.cpython-3{10,11,12,13}-x86_64-linux-gnu.so   set-packing solver
    ogc_fast.cpp / cranepack.cpp                           sources for the above

REBUILDING (only if the binaries need to be regenerated)
-------------------------------------------------------
Requires g++ with C++17 and OpenMP, and pybind11 (pip install pybind11).  Run beside the sources;
the .so files must end up next to myalgorithm.py, which imports them by name.

    g++ -O3 -shared -std=c++17 -fPIC -fopenmp $(python3 -m pybind11 --includes) \
        ogc_fast.cpp  -o ogc_fast$(python3-config --extension-suffix)
    g++ -O3 -shared -std=c++17 -fPIC -fopenmp $(python3 -m pybind11 --includes) \
        cranepack.cpp -o cranepack$(python3-config --extension-suffix)

Without OpenMP, drop -fopenmp: the pragmas become no-ops.  cranepack's conflict-graph build is
parallel and falls back to the serial path with one thread; CRANEPACK_SERIAL=1 forces it, and
both produce the same graph (verified by edge count, 133,863,098 on a 43,320-column build).

DEPENDENCIES
------------
numpy and ortools are used.  pyclipper and scipy are optional -- absent, the code takes an
equivalent path that does not need them.
TXT
( cd $S && zip -q -r "[OGC2026_AlgorithmCode].zip" . -x "[OGC2026_AlgorithmCode].zip" )
echo "== zip 내용이 트리와 바이트 단위로 같은지 =="
TMP=$(mktemp -d); unzip -q $S/"[OGC2026_AlgorithmCode].zip" -d $TMP
BAD=0
for f in myalgorithm.py bayrepack.py utils.py cranepack.cpp ogc_fast.cpp; do
  cmp -s "$f" "$TMP/$f" && echo "  OK   $f" || { echo "  DIFF $f"; BAD=1; }
done
for f in cranepack.cpython-3*.so ogc_fast.cpython-3*.so; do
  cmp -s "$f" "$TMP/$f" && echo "  OK   $f" || { echo "  DIFF $f"; BAD=1; }
done
[ $BAD -eq 0 ] || { echo "ZIP DOES NOT MATCH THE TREE"; exit 1; }
echo "== 빈 디렉터리 클린룸 =="
cd "$TMP"
env -u PYTHONPATH /usr/bin/python3.12 - <<'PY'
import sys, os, json, importlib
sys.path = [p for p in sys.path if p not in ('', os.getcwd())]
sys.path.insert(0, os.getcwd())
import ogc_fast, cranepack, myalgorithm
here = os.path.realpath(os.getcwd())
for m in (ogc_fast, cranepack, myalgorithm):
    assert os.path.realpath(m.__file__).startswith(here), (m.__name__, m.__file__)
print("  확장 모듈이 zip 디렉터리에서 해결됨:", os.path.basename(ogc_fast.__file__))
d = json.load(open(sys.argv[0] if False else "/home/user/oraclemaster/research/exact_packer/session2/recon/data/stage2/prob_24.json"))
s = myalgorithm.algorithm(d, 25)
import utils
c = utils.check_feasibility(d, s)
# A smoke test, not a quality check: 25 s is far under any real budget.  It asserts only
# feasibility, because the value is not stable across engine changes and should not be.
#
# It moved once, and the move is worth recording.  Before the beam learned to complete its
# best partial on expiry, this returned 647,922,415 -- a preference-greedy answer with Z3 1
# and Z1 194,385, which is what a worker falls back to when the beam gives it nothing.  It
# now returns 2,788,156, a factor of 232.  prob_24 is 150 blocks and results/audit/cliff.md
# had it clearing the cliff by 60 s; at 25 s it evidently did not, so the salvage moved the
# usable floor further down than that table measured.
print("  P24 25s  obj=%.0f  feasible=%s   (pre-salvage build at 25s: 647,922,415)"
      % (c["objective"], c["feasible"]))
assert c["feasible"]
PY
echo "== 완료 =="
cd - >/dev/null
ls -la "$S/[OGC2026_AlgorithmCode].zip"
