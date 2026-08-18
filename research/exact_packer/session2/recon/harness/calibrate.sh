#!/bin/bash
# IS OUR LOCAL MEASUREMENT THE SAME RULER AS THE COMPETITION'S?
#
# The question came from the leaderboard.  The leader scores about 2,200,000 on P4 and about
# 70,000 on P3.  Our best P4 arm measures 1,780,253 -- better than the leader -- while our P3
# measures 90,545, well behind.  Beating the leader on one instance and losing badly on another
# is possible, but it is exactly the shape of a measurement that is not comparable, and it must
# be checked before any of today's numbers are used to decide anything.
#
# What checks out already:
#
#   THE FORMULA.  utils.py is the official scorer.  Our P4 result reproduces by hand:
#   13333*88 + 7*2707 + 150*3920 = 1,173,304 + 18,949 + 588,000 = 1,780,253.
#   THE INSTANCES.  P3 200 blocks / 3 bays, P4 150 / 3, P5 200 / 4, P6 250 / 3, and the score
#   magnitudes match the leaderboard's (P3 in the tens of thousands, P4 in the millions).
#
# What does NOT check out yet is the RULER: cores, clock speed, and time limit.  We run four
# workers on this container; the grader's machine is not this machine.  Every number today is
# local.
#
# THE CALIBRATION POINT.  mkbase.py's own header records a score from the real grader:
#
#     "myalg_orig.py is c80551b verbatim -- the build that scored 29396046 on the real P6 at 900s"
#
# So run that exact build on P6 at 900 s here.  Near 29,396,046 means the rulers agree and our
# P4 really is ahead of the leader's.  Far from it means the local machine is more (or less)
# generous than the grader, every comparison today needs rescaling, and "we beat the leader on
# P4" is not a claim that survives.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

python3.12 -c "
import inspect, myalg_orig as O
s = inspect.getsource(O)
assert 'bayrepack' not in s, 'the calibration build must be c80551b as it was, with no brk'
print('calibration build verified: myalg_orig, no brk')" || exit 1

echo "=== the real grader gave this build 29,396,046 on P6 at 900s"
python3.12 harness/run1.py myalg_orig 6 900 "CAL orig P6" > results/cal_orig_p6.log 2>&1
tail -1 results/cal_orig_p6.log
( cd ../../.. && git add -f research/exact_packer/session2/recon/results/cal_orig_p6.log >/dev/null 2>&1 \
  && git commit -q -m "calibration: c80551b on local P6 against the real grader's 29,396,046" >/dev/null 2>&1 \
  && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
echo "calibrate done  $(date -u +%H:%M:%S)"
