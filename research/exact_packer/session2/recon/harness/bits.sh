#!/bin/bash
# THE FREE-COLUMN BITSET, then the P6 re-run that the keepalive hook destroyed.
#
# The search had never been profiled.  When it was:
#
#     build   26,924,021 reads in 50 s
#     search  12,791,335,136 reads in 35 s        475x the build, unexamined
#
# and nearly all of it is one line, in greedy_extend and again inside try_swap:
#
#     for(int c : colsOfBlock[b]) if(blocked[c]==0) { ...; break; }
#
# ~404 candidate positions per block on P3, scanned linearly to answer "which column of this
# block is free".  blocked[] only crosses zero inside add_col/rem_col, so those two can maintain
# one bit per column -- 64 columns to a word, per block -- and the scan becomes ctz over about
# seven words.  Nothing about which column is chosen changes: it is still the first free one in
# the same order, so the placement must come out identical or the change is wrong.
#
# ORDER, and why the identity test comes first.  A faster search under a deadline does not
# finish sooner, it does MORE passes and returns a different answer -- so a full run cannot
# distinguish "faster" from "different".  bitspeed.py unbinds the deadline, runs the identical
# fixed pass sequence in both arms, and compares the placement element by element.  If that says
# DIFFERS the speed number is worthless and the change is reverted, so it is measured first.
#
# THEN P6.  The 900 s P6 run under the ask fix finished at 04:38 and its result line was
# destroyed two minutes later by keepalive.sh, which ran `git reset --hard FETCH_HEAD` on a
# SessionStart:compact while the queue was live and rewound results/af_p6.log to its committed
# partial.  keepalive now refuses to touch the tree while the experiment lock is held.  The
# measurement itself was never in doubt -- it just has to be taken again.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }

echo "waiting for the experiment lock $(date -u +%H:%M:%S)"
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1                     # blocking: queues behind askfix
echo "lock acquired $(date -u +%H:%M:%S)"

grep -q 'CRANEPACK_NOBITS' cranepack.cpp || { echo "bitset not in source"; exit 1; }

echo "== rebuilding cranepack with the bitset $(date -u +%H:%M:%S)"
# flags identical to build_submission.sh, or the A/B measures a compile rather than the change
g++ -O3 -shared -std=c++17 -fPIC -w $(python3.12 -m pybind11 --includes) \
    cranepack.cpp -o cranepack.cpython-312-x86_64-linux-gnu.so || exit 1
python3.12 -c "import cranepack; print('module loads')" || exit 1

echo "== identity + speed $(date -u +%H:%M:%S)"
python3.12 harness/bitspeed.py 2>&1 | tee results/bitspeed.log

( cd ../../.. && git add -f research/exact_packer/session2/recon/results/bitspeed.log \
  && git commit -q -m "bitset: identity and search speed" >/dev/null 2>&1 \
  && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )

run () {  # prob secs tag outfile
    [ -s "results/$4" ] && return
    echo "=== $4 ($3) $(date -u +%H:%M:%S)"
    BRK_DEBUG=1 timeout $(( $2 * 5 + 300 )) \
        python3.12 harness/run1.py myalg_brk "$1" "$2" "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "result: $3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run 6 900 "askfix P6 rerun" "af_p6b.log"
run 3 240 "bits P3"         "bits_p3.log"
echo "bits done $(date -u +%H:%M:%S)"
