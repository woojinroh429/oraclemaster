#!/bin/bash
# _n/ is gitignored, and this container has died three times in one session.  Mirror the run
# log into a tracked file and push whenever it grows, so an hour of P6 measurement survives a
# restart.  Commits can collide with an interactive one, so retry rather than lose the write.
cd "$(dirname "$0")/.."
SRCDIR=_n
last=""
while true; do
  if compgen -G "$SRCDIR/*.log" >/dev/null; then
    cur=$(cat "$SRCDIR"/*.log | md5sum | cut -d' ' -f1)
    if [ "$cur" != "$last" ]; then
      cp "$SRCDIR"/*.log results/
      for i in 1 2 3 4 5; do
        if git add -f results/ && git commit -q -m "measurement logs" 2>/dev/null; then
          for j in 1 2 3 4; do git push -q origin HEAD && break || sleep $((2**j)); done
          last=$cur; break
        fi
        git diff --quiet HEAD -- results/ && { last=$cur; break; }   # genuinely nothing to commit
        sleep 5
      done
    fi
  fi
  sleep 45
done
