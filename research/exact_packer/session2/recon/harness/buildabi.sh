#!/bin/bash
# Build both extensions for every interpreter the grading image might be, and stamp each binary
# with the hash of the source it came from.
#
# The package ships four ABI-tagged copies of each extension because a CPython extension is
# invisible to an interpreter it was not built for, and myalgorithm catches that ImportError and
# returns a legal pure-Python answer roughly 45x worse with no warning.  Four files, though, are
# four things that can drift: on 08-05 the beam's salvage and the OGC_BEAMAIM knob went into
# ogc_fast.cpp, only the 3.12 binary was rebuilt, and the other three sat two days stale in the
# tree waiting to be packaged.  Nothing would have reported it.
#
# So the source hash is compiled in (-DOGC_SRC_SHA) and harness/mkzip.sh greps every .so for the
# hash of the .cpp beside it.  A stale binary now fails the package build.
#
#   usage:  bash harness/buildabi.sh [module ...]      default: ogc_fast cranepack
#   env  :  ABIS="3.12"     restrict to some interpreters
#           NICE=1          build at nice 19, for when measurements are running
set -u
cd "$(dirname "$0")/.." || exit 1

MODS=${*:-"ogc_fast cranepack"}
ABIS=${ABIS:-"3.10 3.11 3.12 3.13"}
PRE=""; [ "${NICE:-0}" = 1 ] && PRE="nice -n 19"

rc=0
for m in $MODS; do
  SHA=$(sha1sum "$m.cpp" | cut -c1-12)
  for v in $ABIS; do
    PY=/usr/bin/python$v
    [ -x "$PY" ] || { echo "  skip $m $v  (no $PY)"; continue; }
    INC=$($PY -m pybind11 --includes 2>/dev/null) || { echo "  skip $m $v  (no pybind11)"; continue; }
    EXT=$($PY-config --extension-suffix)
    OUT="$m$EXT"
    if grep -qa "OGCSRC=$SHA" "$OUT" 2>/dev/null; then
      echo "  ok   $OUT  already at $SHA"
      continue
    fi
    echo "  make $OUT  <- $m.cpp @ $SHA"
    $PRE g++ -O3 -shared -std=c++17 -fPIC -fopenmp -w \
        -DOGC_SRC_SHA="\"$SHA\"" $INC "$m.cpp" -o "$OUT.tmp" || { echo "  FAIL $OUT"; rc=1; continue; }
    # Only replace a working binary once the new one exists, so a failed build never leaves the
    # tree without an extension -- that is the state that produces a silent 45x regression.
    mv "$OUT.tmp" "$OUT"
    grep -qa "OGCSRC=$SHA" "$OUT" || { echo "  FAIL $OUT: stamp missing after build"; rc=1; }
  done
done

echo "== stamps =="
for m in $MODS; do
  SHA=$(sha1sum "$m.cpp" | cut -c1-12)
  for f in $m.cpython-3*.so; do
    [ -e "$f" ] || continue
    if grep -qa "OGCSRC=$SHA" "$f"; then echo "  OK    $f  $SHA"
    else echo "  STALE $f  (wants $SHA)"; rc=1; fi
  done
done
exit $rc
