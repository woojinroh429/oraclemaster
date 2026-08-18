#!/bin/bash
# The one P3 question nothing has asked: is bay 0 FULL, or merely badly packed?
#
# Every check so far -- p3time, p3swap, p3max, ejecthid -- asked whether an outsider fits around
# bay 0's residents AT THE POSITIONS THE PIPELINE GAVE THEM.  All of them said no, and none of
# them could say why, because a block that does not fit around one arrangement has been told
# nothing about a different one.  Bay 0 is at 54% area occupancy, so half of it is empty; what
# refuses the newcomers is the descent rule, and a layout can satisfy that rule for its own
# occupants while fragmenting every column a newcomer needs.
#
# p3bay0.py frees every position and every entry time in bay 0 and lets cranepack -- the
# weighted set-packing search validated against Gurobi earlier in this project -- seat as much
# value as it can.  Two grid resolutions, because step 4 on a 43x23 bay may be too coarse to
# find the seats and step 2 is four times the columns.
#
# The answer decides where the rest of P3 goes.  Nothing admitted: bay 0 is at its crane-rule
# capacity, the 47,954 assignment bound is unreachable, and what is left is Z2.  Five or more
# admitted: packing one bay properly is worth more than every scoring knob tried this session.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

r () {  # tag outfile  env...
    [ -s "results/$2" ] && return
    echo "=== $2  ($1)  $(date -u +%H:%M:%S)"
    env "${@:3}" python3.12 harness/p3bay0.py 3 240 myalg_base 120 > "results/$2" 2>&1
    tail -4 "results/$2"
    ( cd .. && git add -f "session2/recon/results/$2" >/dev/null 2>&1 )
}

r "step 4, 40 outsiders" p3bay0_s4.log STEP=4 NOUT=40 NENT=3
r "step 2, 40 outsiders" p3bay0_s2.log STEP=2 NOUT=40 NENT=3
r "step 2, 80 outsiders" p3bay0_s2n80.log STEP=2 NOUT=80 NENT=4
echo "queue6done  $(date -u +%H:%M:%S)"
