# Reference submission (friend's `submission_v20.2`)

Competitor reference for the OGC 2026 shipyard block packing/scheduling problem,
shared by the user for methodology analysis. Kept here so its techniques can be
studied and, where they win, ported into our pipeline.

## Contents
| file | size | role |
|------|------|------|
| `myalgorithm.py` | 28 KB | entry point (`algorithm(prob, timelimit)`) |
| `beamsolver.py` | 152 KB | **the core** — beam search construction/refinement |
| `gridsolver.py` | 28 KB | grid-based packing/placement helper |
| `native_kernel.py` | 42 KB | Python side of the C++ kernel + fallbacks |
| `parallel_multi.py` | 30 KB | multi-worker orchestration + time budget |
| `ogc_core.*.so` | 777 KB | compiled C++ accelerator (`import ogc_core`) |
| `utils.py` | 64 KB | the official grader (identical to ours) |

## Reference grader scores (target)
```
P1: 11280.0      P2: 31368.0      P3: 93395.0
P4: 2460584.0    P5: 10128108.0   P6: 32366596.0
```
Friend wins P1–P5 vs our current submission; we win P6 (they cannot solve
ultra-dense). Key study target: **why P5 (high-density, Z1-dominated) scores well.**

Runs close to the full ~500 s budget.
