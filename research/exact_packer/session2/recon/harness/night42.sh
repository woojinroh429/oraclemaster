#!/bin/bash
# shadow=1.5 won P5 by 0.81% and passed the deployed build.  Before it can be adopted it has to
# clear two things it has not been asked yet.
#
#   P4 at 1.5   P4's score is settled at 1,780,253 and is the one we cannot afford to lose.  A
#               term that helps P5 and costs P4 is overfitting, and adopting it would be a net
#               loss whatever it does on P5.
#   P5 at 4.0   0.0 and 0.5 tied and 1.5 moved, so the term has a threshold rather than a slope.
#               Where it turns back over matters -- if 4.0 is better still, 1.5 is not the answer,
#               and if 4.0 collapses, 1.5 sits near an edge and is fragile.
#   P3 at 1.5   free to check and the remaining instance; Z1 there is 0, so this is a clean read
#               of what the term does to Z2/Z3 alone.
#
# The engine here is the shadoww build, which is a superset: shadoww defaults to 0.0 and the
# added branch is dead when it is, so shadow behaves exactly as it did in night40.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
EXT="cpython-312-x86_64-linux-gnu.so"
cp "/tmp/ogc_shadw.$EXT" "/tmp/st6.$EXT" && mv "/tmp/st6.$EXT" "ogc_fast.$EXT"
for SH in 1.5 4.0; do
    python3.12 harness/mkbase.py 0.3 "myalg_sh${SH/./_}.py" "$SH" > /dev/null || exit 1
done
python3.12 harness/mkbase.py 0.3 myalg_sh0_0.py 0 > /dev/null || exit 1
echo "arms built  $(date -u +%H:%M:%S)"

run () {  # prob limit shadow
    out="results/shad_p${1}_${3}.log"
    [ -s "$out" ] && return
    echo "=== P$1 shadow=$3 (${2}s)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "myalg_sh${3/./_}" "$1" "$2" "shadow=$3" > "$out" 2>&1
    tail -1 "$out"
    ( cd .. && git add -f "session2/recon/$out" >/dev/null 2>&1 )
}
# P3 first: it is the cheapest pair (240s each) and the instance that is most stuck, so it is
# the fastest read on whether shadow generalises at all.  Its Z1 is 0, so it also isolates what
# the term does to Z2/Z3 with tardiness out of the way.
run 3 240 0.0
run 3 240 1.5
run 4 480 0.0        # P4 control on this engine
run 4 480 1.5        # the overfitting check that decides adoption
run 5 600 4.0        # where the term turns
echo "done  $(date -u +%H:%M:%S)"
