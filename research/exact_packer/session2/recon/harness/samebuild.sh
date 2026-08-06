#!/bin/bash
# Compare the SOURCE change, not two differently-produced binaries.
#
# THE FLAW THIS FIXES.  rebuild.sh and abvar compared the tree's shipped .so against a fresh build
# of the patched source.  Those two binaries differ by more than the patch: the shipped one came
# from buildabi.sh with -DOGC_SRC_SHA=<hash>, the new one from a plain g++ line without it, built
# by a different invocation at a different time.  Code layout and speed differ, and this search is
# wall-clock dependent -- a proved bit-identical 1.85x speedup once moved an objective by 7.7%.  So
# a difference in that comparison cannot be attributed to the patch.
#
# The reasoning also does not survive inspection.  A run that did not crash is a run whose top-up
# pass never executed: the pass rescans keyed from index 0, so its first pick is whatever the quota
# pass already took, and moving that a second time puts a hollow state into the beam which the next
# level always faults on.  Survive => the pass never ran => the patch is a no-op for that run.  Yet
# abvar shows P12 consistently 3.4% apart across replicates, at 0.23% internal spread.  Something
# other than the patch is producing that, and the build is the obvious candidate.
#
# So: build BOTH sources with the SAME command line into sibling trees.  Pre-patch ogc_fast.cpp
# comes from f65ea0b^ -- the commit that introduced the fix -- so "old" is the exact code that was
# running, not a reconstruction.  Everything else (myalgorithm.py, bayrepack.py, cranepack.so) is
# shared by symlink, so the only difference between the trees is the one hunk.
set -u
cd "$(dirname "$0")/.." || exit 1
R=$(pwd)
L=results/audit/samebuild.log
mkdir -p results/audit; touch $L
echo samebuild > harness/CURRENT

FIX=f65ea0b        # "ogc_fast: stop moving the same beam state twice"
SRC=research/exact_packer/session2/recon/ogc_fast.cpp

if [ ! -d build_pre ]; then
    mkdir -p build_pre
    ( cd "$(git rev-parse --show-toplevel)" && git show "$FIX^:$SRC" ) > build_pre/ogc_fast.cpp || exit 1
    echo "pre-patch source: $(sha1sum build_pre/ogc_fast.cpp | cut -c1-12)" >> $L
    echo "post-patch source: $(sha1sum ogc_fast.cpp | cut -c1-12)" >> $L
    diff <(git -C "$(git rev-parse --show-toplevel)" show "$FIX^:$SRC") ogc_fast.cpp \
        | head -60 >> $L
fi

# IDENTICAL COMMAND LINES.  The only difference permitted between the two binaries is the .cpp.
build(){ # srcdir outdir
    local sfx
    sfx=$(python3.12-config --extension-suffix)
    mkdir -p "$2"
    g++ -O3 -shared -std=c++17 -fPIC -fopenmp $(python3.12 -m pybind11 --includes) \
        "$1/ogc_fast.cpp" -o "$2/ogc_fast$sfx" 2>>$L || return 1
}
link(){ # dir
    ( cd "$1" || exit 1
      for f in myalgorithm.py bayrepack.py utils.py harness data; do
          [ -e "$f" ] || ln -s "../$f" "$f"; done
      for f in "$R"/cranepack.cpython-*.so; do ln -sf "$f" .; done )
}

echo "== build both from the same command line ==" >> $L
build build_pre build_pre || { echo "PRE BUILD FAILED" >> $L; exit 1; }
build "$R"     build_post || { echo "POST BUILD FAILED" >> $L; exit 1; }
link build_pre; link build_post
echo "  pre  $(sha1sum build_pre/ogc_fast.cpython-312-x86_64-linux-gnu.so | cut -c1-12)" >> $L
echo "  post $(sha1sum build_post/ogc_fast.cpython-312-x86_64-linux-gnu.so | cut -c1-12)" >> $L

run(){ # rep arm prob
    local tag="r$1.$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    ( cd "build_$2" && OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 \
        "[$tag]" --data data/stage2 ) >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/samebuild.log \
      && git commit -q -m "in-flight: samebuild $tag" ) >/dev/null 2>&1
}

# P12 first: it is where abvar showed a consistent gap, so it is the claim under test.
for rep in 1 2 3 4 5; do
    for p in 12 3 1 26 30 6 16 20; do
        run $rep pre $p
        run $rep post $p
    done
    echo "REPDONE $rep" >> $L
done
echo "SAMEBUILDDONE" >> $L
echo idle > harness/CURRENT
