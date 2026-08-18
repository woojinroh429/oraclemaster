# The fourth submission is the third submission, and that is the most useful thing we have

Submitted 2026-08-06 17:01:17 UTC.  Zip as sent, verified against the third submission's package
(commit `62c423d`, submitted 08-05):

| file | difference |
|---|---|
| `ogc_fast.cpp` | **0 non-comment lines** |
| `myalgorithm.py` | **1 non-comment line** — inside a docstring: `"A competitor's"` -> `"An alternative"` |
| `bayrepack.py`, `utils.py` | byte-identical |

That is commit `85ad78c` (08-06 01:59, attribution wording removed) and nothing else.  The `.so`
files differ only because `OGC_SRC_SHA` is compiled in and the comment change moved the source
hash.  **No algorithmic change of any kind.**

## Therefore: the same algorithm, drawn twice on the real hidden set

| inst | 1st | 2nd | 3rd | 4th | 4 vs 3 |
|---|---|---|---|---|---|
| P1 | 3,068,862 | 3,328,237 | 2,847,060 | 2,875,074 | +0.98% |
| P2 | 19,829,534 | 20,337,489 | 20,063,787 | 20,164,596 | +0.50% |
| P3 | 5,886,589 | 5,867,652 | 5,613,271 | 5,856,298 | +4.33% |
| P4 | 4,421,375 | 4,283,430 | 4,681,440 | 4,439,801 | -5.16% |
| P5 | 6,308,099 | 6,104,015 | 6,148,480 | 6,109,330 | -0.64% |
| P6 | 1,024,046 | 1,053,770 | 968,674 | 1,052,516 | **+8.66%** |
| P7 | 16,385,030 | 16,285,457 | 16,310,765 | 15,807,529 | -3.09% |
| P8 | 17,079,881 | 16,023,014 | 17,347,930 | 16,695,656 | -3.76% |
| **total** | 74,003,416 | 73,283,064 | 73,981,407 | **73,000,800** | **-1.33%** |

4 better, 4 worse, median -0.07%, range -5.16% to +8.66%.

## The submission noise floor, measured

**Per instance +-8.7%.  On the total +-1.3%.**  Against that:

    1st -> 2nd   -0.97%
    2nd -> 3rd   +0.95%
    3rd -> 4th   -1.33%     <- zero code change

All three are the same size.  **No comparison of submitted totals has ever been able to see an
algorithmic change**, including this report's own "1 -> 3 = -0.0%", which was read as "the work
bought nothing" and actually says "the instrument has no resolution".

The fourth total is the best of the four.  That is luck, not quality: the code is the third's.

This also confirms on the GRADER, not on our container, what
`results/audit/variance_source.md` deduced from the source: every RNG in the algorithm is
constant-seeded, so the only input that differs between two runs is `time.time()`, and here that
alone moved a hidden instance by 8.66%.

## Consequences

1. Stop reading submitted totals as measurements.  40-instance paired runs on `data/stage2` are
   the only instrument with the resolution to see a few-percent change.
2. The tail, not the median, is what an 8-instance score pays for.  A +8.66% draw on one instance
   costs more than any median improvement measured this project has bought.
3. **The submitted zip does NOT contain the segfault fix.**  `ogc_fast.cpp:2117`
   (`std::vector<char> moved(children.size(),0)`) is present in
   `submit_final/[OGC2026_AlgorithmCode]_kgu_mis_21.zip` and absent from what was sent.  That bug
   crashes a worker inside `contact_beam`; the third submission's `pool.map` then waits forever
   and the instance scores nothing.  All eight came back feasible this time.  The next submission
   must be the `submit_final/` package.
