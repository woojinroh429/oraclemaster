#!/bin/bash
# _n/ is gitignored, and this container has died three times in one session.  Mirror the run
# log into a tracked file and push whenever it grows, so an hour of P6 measurement survives a
# restart.  Commits can collide with an interactive one, so retry rather than lose the write.
cd "$(dirname "$0")/.."
SRC=_n/p6full.log
DST=results/p6_cohort_baseline.log
last=""
while true; do
  if [ -f "$SRC" ]; then
    cur=$(md5sum "$SRC" | cut -d' ' -f1)
    if [ "$cur" != "$last" ]; then
      cp "$SRC" "$DST"
      for i in 1 2 3 4 5; do
        if git add -f "$DST" && git commit -q -m "P6 measurement log: cohort effect at the 29.4M baseline" 2>/dev/null; then
          for j in 1 2 3 4; do git push -q origin HEAD && break || sleep $((2**j)); done
          last=$cur; break
        fi
        git ls-files --error-unmatch "$DST" >/dev/null 2>&1 \
          && git diff --quiet HEAD -- "$DST" && { last=$cur; break; }   # genuinely nothing to commit
        sleep 5
      done
    fi
  fi
  sleep 45
done
