#!/bin/bash
# THE PACKER, not the weights.  Does a (k,1) ejection move pay inside a real run?
#
# WHAT WAS ACTUALLY WRONG.  cranepack's local search has exactly two improving moves, (1,1) and
# (2,1), and BOTH remove exactly one selected column.  Worse, the candidates they will even look
# at are restricted to blocked[c]==1 -- columns blocked by that single column alone.  A column
# blocked by TWO selected columns is unreachable from either of them.  So wherever seating a
# block needs two or more evictions, the neighbourhood is EMPTY however the weights are set.
#
# That is the whole P3 story and the evidence is now flat.  Under three different weightings --
# single-move deltas, directed-wish deltas from an exact reassignment, and exact linearised
# coefficients -- the trace was identical to the block:
#
#     brk tgt=0 res=55 outs=15  seated 55 of 70 columns, admitted NO outsider
#
# Three weightings agreeing to the digit is not a weighting problem.  Adding the guided ejection
# changed it on the first try, on the same converged incumbent:
#
#     admitted 2, displaced 3, obj 99090 vs base 86665 -> reject
#
# Rejected on the true objective, which is the grader doing its job -- but the neighbourhood is
# no longer empty.  That converged 86,665 point is the one place brk is guaranteed to find
# nothing (brk ran inside the pipeline that produced it), so this measures the change where it
# can actually pay: many calls, rotating seeds, states the operator has not already settled.
#
# THREE ARMS so a win is attributable.  eject+linw, eject alone, and the shipped behaviour.
# Same module and same binary throughout; the arms differ only by environment, because arm
# levels have drifted between separately generated modules twice tonight.
#
# NOT A P3 SPECIAL CASE.  The ejection is a general repair of an incomplete local search: it
# fires wherever a heavy block is blocked by several light ones, and the weight test that
# guards it is the same objective the operator is already scored against.  On an instance where
# single eviction suffices it simply never has a cheaper option to find.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, bayrepack as R
a = inspect.getsource(A); r = inspect.getsource(R)
assert 'import bayrepack as _brk' in a and 'hard=budget - (time.time() - t0)' in a
assert 'BRK_LINW' in r and '_z2c' in r, 'linearised weights missing'
import cranepack, subprocess
src = open('cranepack.cpp').read()
assert 'CRANEPACK_EJECT' in src and 'try_eject' in src, 'ejection move missing from the source'
print('arm, operator and packer verified')" || exit 1
# The .so must be NEWER than the source, or the queue measures the previous binary -- a
# container restart has already reverted an engine .so once tonight and four queues reported
# the greedy floor as an ordinary result before anyone noticed.
[ cranepack.cpython-312-x86_64-linux-gnu.so -nt cranepack.cpp ] \
    || { echo "cranepack .so is older than cranepack.cpp -- rebuild first"; exit 1; }

run () {  # eject linw tag outfile
    [ -s "results/$4" ] && return
    echo "=== $4  ($3)  $(date -u +%H:%M:%S)"
    CRANEPACK_EJECT="$1" BRK_LINW="$2" \
        python3.12 harness/run1.py myalg_brk 3 240 "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "result: $3" >/dev/null 2>&1 )
}

for rep in 1 2; do
    run 1 1 "eject+linw r$rep" "q29_el_r${rep}.log"
    run 1 0 "eject only r$rep"  "q29_ej_r${rep}.log"
    run 0 0 "shipped    r$rep"  "q29_ctl_r${rep}.log"
done
echo "queue29done  $(date -u +%H:%M:%S)"
