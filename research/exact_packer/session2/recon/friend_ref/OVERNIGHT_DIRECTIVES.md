# Overnight standing directives (user, keep honoring these)

Persisted here so a container restart / context compaction can't lose them.

## Optimization philosophy
- **Generalize, don't overfit.** Accept small per-instance regressions (~3–5%) if the
  change is a robust general improvement ("가불기" — a fair trade-off). Do NOT obsess over
  protecting every single instance; optimize the WHOLE.
- **But raise the overall score.** The trade must be net-positive across the set.
- Beam on EVERYTHING except ultra-high-density (done: OGC_BROADBEAM, ultra = phys demand ≥0.90).
- Scoring must be OURS, not a verbatim copy of the friend's (done: OGC_OURSCORE, crane-aware).

## Standing work queue
1. Finish in-flight experiments → **commit+push everything that wins net**.
2. **Speed**: profile the beam search, find bottlenecks, accelerate the slow paths.
3. **Levers**: thoroughly hunt for further score-improvement levers.
4. Validate broadly incl. prob_1-20; low-density gets heavy experimentation.

## Real grader results (user's submission = commit 61b97e5, pre-broadbeam)
| set | ours | friend | note |
|-----|------|--------|------|
| P1 | 11,280 | 11,280 | tie |
| P2 | 31,368 | 31,368 | tie |
| P3 | 90,545 | 93,395 | **we win** (but flat vs user's prev → was gated out of beam) |
| P4 | 3,009,682 | 2,460,584 | friend wins (much improved vs user's prev) |
| P5 | 11,501,940 | 10,128,108 | friend wins |
| P6 | 28,742,380 | 32,366,596 | **we win** (friend can't solve ultra-dense) |
Targets to beat: P4, P5. P3 flat because beam was gated out (now fixed by broadbeam).

## Hard constraints (never violate)
- Branch: claude/repair-plan-model-1ig6it, push -u origin with backoff retries.
- Commit trailers: Co-Authored-By: Claude Opus 4.8 + Claude-Session line. NO model id in artifacts.
- friend ogc_core.so was lost to a restart (upload gone); friend .py sources are committed.
  Re-request the zip from the user only if the friend engine must run again.
- scipy needed for friend code (`pip install --break-system-packages scipy`).
