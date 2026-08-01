#!/bin/bash
# Reach a DIFFERENT solution, because there is no variance left to remove.
#
# WHAT q23 SETTLED.  With the tier fix in, the arm is deterministic on P3: three control runs
# returned 86,665 with Z2=3023 and Z3=477 every time, spread zero.  The 9,490 spread quoted all
# night mixed queues whose CODE differed -- the tier rule, the ask deflation and the `hard`
# argument all landed between them -- so it was never a property of one build.  The warm-up arm
# actually made things worse (88,695 / 88,630 / 86,665): throwing a beam away perturbs the cache
# and moves later calls into other basins, the opposite of what I expected it to do.
#
# So the problem is no longer "the answer moves".  It is "the answer sits at 86,665".
#
# WHERE A DIFFERENT ANSWER COULD COME FROM.  brk works because an arrangement a greedy pass
# committed to can be re-solved exactly -- and a DIFFERENT arrangement re-solves differently.
# The pipeline already keeps up to six distinct solutions per worker in pool[], and brk only
# ever repacks pool[0].  Rotating over the first two or three costs nothing: the pool is already
# built and already scored, and whatever comes back still has to beat the incumbent on the real
# grader, so a worse starting point can only waste its own slice.
#
# This is also the only remaining lever with an argument behind it.  Contact weakening is closed
# four ways, span2 is the same mechanism, hmatch is unestablished on top of brk, throughput moved
# 0.26%, BRKGA is drowned by evaluation noise, and free repacking is being re-measured from a
# good start in queue25.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
# ONE INSTANCE PER QUEUE.  The shared experiment lock serialises DIFFERENT queues but not
# a second copy of THIS one -- two copies simply take it in turn and overwrite each
# other's result files, which is exactly what contaminated q23 (see
# results/contaminated/README.txt).
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
for P in 2 3; do
    OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_BRKPOOL="$P" \
        python3.12 harness/mkbase.py 0.3 "myalg_bp${P}.py" 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
done
python3.12 -c "
import inspect, myalg_brk as C, myalg_bp2 as A, myalg_bp3 as B
c, a, b = (inspect.getsource(m) for m in (C, A, B))
assert 'pool[0][1], t, _total' in c, 'control must repack the incumbent only'
assert 'pool[min(_brk._CALLS[0] % 2, len(pool) - 1)][1]' in a
assert 'pool[min(_brk._CALLS[0] % 3, len(pool) - 1)][1]' in b
print('pool-rotation arms verified: incumbent-only / rotate 2 / rotate 3')" || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2 3; do
    run myalg_brk "pool0 r$rep"    "q26_p0_r${rep}.log"
    run myalg_bp2 "pool rot2 r$rep" "q26_p2_r${rep}.log"
    run myalg_bp3 "pool rot3 r$rep" "q26_p3_r${rep}.log"
done
echo "queue26done  $(date -u +%H:%M:%S)"
