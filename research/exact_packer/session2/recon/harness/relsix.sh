#!/bin/bash
# ALL SIX on the fast build: offset-relative geometry + conflict memo + entry-sorted sweep.
#
#     original build   18,789,635 edges   56.9 s
#     now              18,789,623 edges    5.4 s      10.5x
#
# P3 already answered the question this was built for -- 80,795 on the SLOW host, feas=y, where
# the same host gave 100,685 this afternoon because a 90 s build could not be afforded.  These
# are the other five, plus a P3 repeat.
#
# WHAT WOULD MAKE THIS NOT SHIPPABLE: any instance coming back feas=n.  The offset-relative
# geometry changes twelve edges of 18.8 million -- the touching cases whose old verdict depended
# on where in the bay they sat -- in the more PERMISSIVE direction.  _total re-validates with the
# real grader and returns inf on failure, so a missed conflict costs work rather than
# correctness, but that is an argument, and feas=y on six instances is evidence.
#
# BASELINES on this host: P3 80,795.  Everything else was measured this morning on a host 1.5x
# faster and is not comparable -- these establish the real ones.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

python3.12 -c "
import cranepack as CP
c = open('cranepack.cpp').read()
assert 'crane_conflict_rel' in c and 'ConflictMemo' in c, 'not the fast build'
assert 'poly_overlap_off' in c, 'geometry is not offset-relative'
print('verified: offset-relative geometry + exact conflict memo')" || exit 1

run () {  # prob secs tag outfile
    [ -s "results/$4" ] && return
    echo "=== $4 ($3) $(date -u +%H:%M:%S)"
    BRK_DEBUG=1 timeout $(( $2 * 5 + 300 )) \
        python3.12 harness/run1.py myalgorithm "$1" "$2" "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "relsix: $3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run 6 900 "rel P6" "rl_p6.log"
run 4 480 "rel P4" "rl_p4.log"
run 5 600 "rel P5" "rl_p5.log"
run 1  60 "rel P1" "rl_p1.log"
run 2 120 "rel P2" "rl_p2.log"
run 3 240 "rel P3 r2" "rl_p3_r2.log"
echo "relsix done $(date -u +%H:%M:%S)"
