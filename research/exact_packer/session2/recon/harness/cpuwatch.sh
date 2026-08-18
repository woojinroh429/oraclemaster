#!/bin/bash
# Run a command and report its process tree's PEAK and MEAN CPU percentage alongside it.
#
# WHY A SAMPLER AND NOT `time`.  /usr/bin/time gives total CPU seconds, which divided by wall gives
# the MEAN.  The grader's limit is on instantaneous usage, so the mean can sit at 250% while the
# beam's parallel section spikes over 400% and gets the run killed.  The peak is the number that
# decides, and only sampling produces it.
#
# HOW.  Sample every 0.25 s: sum %cpu over every process whose session leader is our child.  ps
# reports %cpu as CPU-time/elapsed since process start, which UNDERSTATES a late spike -- so the
# per-sample delta of /proc/<pid>/stat utime+jiffies is used instead, which is the true
# instantaneous rate over the sample interval.
#
# usage: cpuwatch.sh <label> <logfile> -- <command...>
set -u
LBL="$1"; LOG="$2"; shift 3
CLK=$(getconf CLK_TCK)
"$@" & CPID=$!
peak=0; sum=0; n=0
declare -A prev
while kill -0 $CPID 2>/dev/null; do
    tot=0
    for p in $(pgrep -g $(ps -o pgid= -p $CPID 2>/dev/null | tr -d ' ') 2>/dev/null); do
        read -r _ _ _ _ _ _ _ _ _ _ _ _ _ ut st _ < /proc/$p/stat 2>/dev/null || continue
        cur=$(( ut + st ))
        if [ -n "${prev[$p]:-}" ]; then tot=$(( tot + cur - prev[$p] )); fi
        prev[$p]=$cur
    done
    if [ $n -gt 0 ]; then
        pct=$(awk -v t="$tot" -v c="$CLK" 'BEGIN{printf "%.0f", t*100.0/(c*0.25)}')
        [ "$pct" -gt "$peak" ] && peak=$pct
        sum=$(( sum + pct ))
    fi
    n=$(( n + 1 ))
    sleep 0.25
done
wait $CPID; rc=$?
mean=0; [ $n -gt 1 ] && mean=$(( sum / (n - 1) ))
echo "# CPU [$LBL] peak=${peak}% mean=${mean}% samples=$n rc=$rc" >> "$LOG"
exit $rc
