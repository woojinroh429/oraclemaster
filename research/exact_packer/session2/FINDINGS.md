# 세션2 — cranepack 오라클 + VLNS 메타휴리스틱 (전체 기록)

목표: cranepack(정확 크레인 set-packing)을 오라클로 하는 순서탐색/VLNS 메타휴리스틱으로
경쟁자 추월. 저밀도(Z3 지배)와 적당한 고밀도 둘 다 실험.

## 인스턴스 세트 (중요 — 이전에 놓쳤던 것)
- `data/training_instances/train/` : prob_1~20 (전부 저밀도, util<1, Z1=0)
- `data/train/` : prob_21~40 (고밀도, util 0.76~2.59; util>1 = 수요>용량 → 혼잡)
- 적당한 고밀도 = util 1.0~1.3: prob_24(1.03), prob_36(1.01), prob_34/35(1.15), prob_21(1.21)
- 초고밀(P5/P6급) = util 2.2~2.6: prob_27, prob_38, prob_40

## 1. cranepack 오라클 (cranepack.cpp) — 완성·검증 ★
순수 C++ (Gurobi/ortools 의존 없음). pybind11, -march=x86-64-v2.
- 입력: clique 블록들(orient별 layers/obb, entry/exit 변형 리스트), bay W/H, step, frozen 장애물, per-block 가중치
- coarse-grid 컬럼 생성 → 쌍별 크레인 충돌(j>=k, fastconf 로직 포팅) → **max-weight MIS**
  (iterated greedy + (2,1)/(1,1) weight-swap local opt + force/repair + kick)
- 검증: prob_20 bay1 clique17 → **10 (Gurobi=10 매칭), 전 시드, bad=0**, ~0.6s
  (Python numba+Gurobi 65s 대비 ~100배)
- Gurobi pairwise 모델은 죽은 길(413k 제약, model-build 5.7s + solve 30s 타임아웃)
- 확장: frozen obstacle 컬럼드롭, per-block 엔트리 변형(재타이밍), per-block 가중치(objective-aware)

## 2. 저밀도 결과 ★★ (진짜 win)
### 격리 A/B (고정 warm) — z3cp.py: OLD _z3_relocate vs cranepack relocate
- best-of(old,crane,stack): prob_20 −6.9%, prob_13 −6.5%, prob_17 −0.3%, prob_19 tie
### standalone VLNS (vlns.py) — 1코어 vs v72 4코어, fresh warm, grader 점수
| inst | VLNS | v72 | |
|---|---|---|---|
| prob_20 | 97125 | 109118 | −11% |
| prob_13 | **72789 (3회 동일)** | 74979 | −2.9% |
| prob_17 | **62841 (3회 동일)** | 68180 | −7.8% |
| prob_19 | 66685 | 65696 | +1.5% |
| 합 | | | **−5.8%** |
- **1코어 VLNS가 4코어 v72를 3/4 이김. 압도적으로 일관적**(변동 없음).
- **핵심 발견: warm 다양성이 결정적.** prob_19: feedback warm→66685(갇힘), **seed warm→58987**
  (이전 최고 62254보다 −5.3%). 즉 "다양한 exact_reassign 모드 → 각각 VLNS 정제 → best-of".

### VLNS 속도 교훈 (중요)
- 처음: iteration 안에서 descent(6-pass) 통째 재실행 → 5 iters/30s (느림)
- 고침: **iteration = cranepack 1회(window_repack)** → 125+ iters/30s (25배)
- window_repack: bay의 작은 시간창(WIN~6) + pull 몇 개를 cranepack이 max-pref-weight로 재패킹
  (저선호 방출 → 고선호/pull 삽입, 순차 삽입이 못하는 재배치). ONE cranepack call.
- 초기 descent(z3_relocate_cp)로 basin 바닥까지 간 뒤 window_repack SLS + stall시 큰 kick.
- best 갱신만 check_feasibility로 검증(cranepack geometry가 grader와 드물게 불일치).

### 통합 (v72/v73) — 미흡
- v72: cranepack relocate를 shake 루프에 추가(짝수 워커만, never-worse). full A/B: −0.7~−1.3%.
- v73: _vlns_refine를 저밀도 tail에. full A/B(5trial): prob_20 −3.1%, prob_17 −7.8%,
  prob_13 +0.3%, **prob_19 +7.1% 퇴행**, 합 −1.3%.
- **문제: 4워커가 compute를 나눠 각 VLNS를 굶기고, best-of가 seed-58987 basin을 못 살림.**
  standalone(−5.8%)의 위력이 희석됨.
- **다음: 저밀도 경로를 "워커 수 줄이고 warm당 full 예산 + seed/feedback best-of"로 재설계.**

## 3. 고밀도 결과 (진단 완료, 부분 win)
- 적당한 고밀도(prob_24/34/35): 중간 해에서 **Z1(지각)이 종종 지배**. 30s 파이프라인이 Z1→~0.
- cranepack/VLNS는 Z3(+Z2)만 줄이고 **Z1은 못 건드림**.
- 결과: **Z1이 이미 낮을 때만 이득** — prob_24(Z1=3) **−3.0%**; prob_35(Z1=51) −0.1%; prob_34(Z1=247) +0%.
- **고밀도 진짜 레버 = Z1(지각) 감소 = entry 스케줄링**("빽빽하게 넣어 더 이른 진입").
  현재 Z3-재배치 move와 다름. 필요: cranepack이 **넓은 entry 후보로 가장 이른 feasible 시각에
  스케줄**하는 tardiness-aware move.

## 파일
- cranepack.cpp : 오라클 (weighted, frozen, entry-variants). 빌드:
  `g++ -O3 -shared -std=c++17 -fPIC -march=x86-64-v2 $(python3.12 -m pybind11 --includes) cranepack.cpp -o cranepack.cpython-312-x86_64-linux-gnu.so`
- vlns.py : standalone VLNS 엔진 (Engine: cp_place/window_repack/ruin_recreate/descent/solve) + 드라이버
- z3cp.py : cranepack relocate 격리 A/B (old vs new)
- hdvlns.py : 고밀도 실험 (파이프라인 warm → VLNS Z3-polish)
- density.py : 밀도/레짐 프로파일러
- myalgorithm_v73.py : _vlns_refine 통합본 (참조; 통합 미흡)

## 다음 세션 착수점
1. (저밀도 win 실현) 저밀도 경로 재설계: 1~2 워커가 exact_reassign(feedback)+exact_reassign(seed)
   각각 full-budget VLNS → best-of. standalone −5.8%/prob_19 58987 재현이 목표.
2. (고밀도) tardiness-aware cranepack move: 넓은 entry 후보 + '이른 feasible entry' 가중치로
   space-time 조밀 스케줄 → Z1 감소. 그 뒤 Z3-polish.
3. 현 제출 최선 = v71 (P3=102625). 통합 win 검증 전까지 유지.

## ★★★ 4. 근본 버그 발견 + v74 (이번 세션 최대 성과) ★★★

### use_cpp NameError — streamlined 경로가 v71 포함 모든 버전에서 크래시
`_streamlined_lowdensity(prob_info, bay_unit, deadline, rng, worker_id)` 함수 본문이
호출자(`_solve_once_impl`)의 지역변수 `use_cpp`를 참조(`_is_guard = ... not use_cpp`)하는데
자기 시그니처엔 없어서 **항상 NameError로 크래시**. 호출부(3696)가 try/except로 삼켜서
**조용히 old 폴백 경로(construction+ALNS)로**. 즉:
- 제출된 v71의 저밀도는 streamlined/exact_reassign이 한 번도 안 돌고 폴백으로 나온 값.
- v72/v73의 cranepack/VLNS 통합 코드는 크래시 지점 뒤라 실행조차 안 됨 (marginal = 폴백 노이즈).
- standalone VLNS(_exact_reassign/_vlns_refine 직접 호출)만 진짜였음.

**수정 = use_cpp를 파라미터로 전달** (시그니처 + 호출부 한 줄씩). 이걸로 streamlined+VLNS가
파이프라인에서 실제로 돌기 시작.

### v74 = use_cpp 수정 + clean 저밀도(shake/ALNS 제거, exact_reassign warm → full-budget VLNS)
저밀도 A/B (v71 vs v74, 5 trial median):
| inst | v71 | v74 | Δ | v74 일관성 |
|---|---|---|---|---|
| prob_20 | 104525 | **87156** | **-16.6%** | 87156 ×5 (동일) |
| prob_13 | 75988 | **72789** | **-4.2%** | 72789 ×5 |
| prob_17 | 62841 | 62841 | 0% | 62841 ×5 |
| prob_19 | 66685 | **58987** | **-11.5%** | 58987 ×5 |
| 합 | 310039 | **281773** | **-9.1%** | |
- **완벽 일관 (매 인스턴스 5회 동일값). v71의 변동(prob_20 98840~110181)이 사라짐.**
- 워커 다양성: 짝=exact_reassign feedback basin, 홀=seed basin. seed 워커가 prob_19의 58987 basin을 염.

고밀도 무회귀 체크 (v71 vs v74, 2 trial):
- prob_24 동일(993419), prob_34 노이즈내(+0.8%), prob_38 -83%(v71 408M outlier 회피), prob_40 -19%.
- streamlined는 temporal_os<0.30 게이트라 Z1-지배 고밀도엔 무영향; 일부 Z3-지배 고밀도는 오히려 안정화.

### v74 파이프라인 구조 (clean 저밀도)
각 저밀도 워커: `exact_reassign(mode, 0.35*budget) → _vlns_refine(나머지 full) → return`.
- _vlns_refine: 초기 descent(z3_relocate_cp, FREE~10) → window_repack SLS(cranepack 1회/iter,
  WIN6/step8/single_entry, 125+ iters/30s) + stall시 ruin_recreate kick. best만 grader 검증(never-worse).
- ALNS/SA-shake/sa_reassign 전부 제거 (저밀도엔 무용, 예산만 씀). cranepack 없으면 기존 shake로 폴백.
- 제출: submit_v74.zip (7파일: myalgorithm, utils, ogc×3, st3dtcs, cranepack).

### 다음
- 광범위 스윕(prob_1~40 대표) 무회귀 최종확인 후 v74 제출.
- (남음) 고밀도 tardiness-aware cranepack move (#44) — Z1-지배 초고밀엔 아직 레버 없음.

## 5. 버그헌트 + 고밀도 최종결론
- **AST undefined-name 스캐너(undef.py)로 v71 전체 스캔**: 진짜 잠재버그는 `use_cpp` 하나뿐.
  `_pyclip`(NFP)도 걸렸으나 호출부가 `_HAVE_PYCLIP`로 게이트된 dead code라 무해.
- **넓은 무회귀 스윕(v71 vs v74, prob_1/8/14/18/24/27/31/36/40)**: 퇴행 0. 오히려
  prob_14 −11.9%, prob_18 −11.3%(저밀도), prob_24 −10.1%, prob_40 −35.2%(고밀도) 개선.
  → **use_cpp 수정이 저·고밀도 불문 Z3-지배 인스턴스를 자동 개선**(streamlined VLNS 도달).
- **고밀도 Z1(지각)은 near-optimal (병렬세션 7730e6f, CP-SAT OPTIMAL 증명)**: 밀도 헤드룸은
  tardiness-무관(늦게 release된 블록은 빽빽이 넣어도 지각 안 줆). prob_27/31/36(Z1-지배)은 v74도 무변.
  → tardiness-aware cranepack(#44)은 **dead-end**. 고밀도 추가 헤드룸 없음.
- **통합**: temporal_os 게이트가 "Z3-지배(VLNS −10~35%) vs Z1-지배(near-optimal)"를 올바르게 분리.
  VLNS는 어디서든 never-worse(prob_31 강제=무변)이므로 구조적 통합 안전하나 Z1-지배엔 무익.

## 최종 제출 = submit_v74.zip (저밀도 -9.1%, 고밀도 무회귀/일부 대폭개선, 완벽 일관)

## 6. Pure-C++ VLNS (v75) + the warm-limited finding
- `cranepack.refine()`: whole low-density SLS in C++ (descent FREE~10 + window-repack +
  ruin-recreate + SA). MIS strengthened with pack()'s force/repair loop + multi-entry +
  fine-grid descent -> ~10-50x more iterations than the Python loop (2600 vs 50).
- v75 = v74 with `_vlns_refine` replaced by ONE `CP.refine()` call (Python SLS removed;
  only a single final check_feasibility guard kept so a rare geometry mismatch can never
  ship an infeasible solution -> returns the feasible warm instead).
- **A/B v74 vs v75 (4-trial median): net -0.2% (EQUIVALENT).** prob_20 -1.8% (v75 wins,
  85558 vs 87156, both consistent), prob_13 +1.5% (v75 loses median but hits 70973 once,
  below v74's best), prob_17 tie, prob_19 tie (v75 hits 56709 once, below v74's 58987).
- **KEY FINDING: low-density is WARM-limited, not refinement-limited.** v75's better
  outliers (70973, 56709) came from different exact_reassign WARMS, not from more SLS
  iterations -- each warm basin has a floor the SLS reaches in ~50 iters, so the 50x C++
  iteration speedup does NOT lower the objective. Multi-restart-from-descent inside
  refine() did not help (confirmed the variance is warm-driven). The remaining lever is
  WARM DIVERSITY (more exact_reassign modes/seeds, or a cheap greedy-warm fan-out that
  the fast C++ refine could each polish + best-of), not faster refinement.
- **Recommendation: v74 stays the ship** (proven -9.1% vs v71, broad-sweep + HD-checked).
  v75 (pure C++) is an equivalent alternative kept for the warm-diversity direction.

## 7. 최종 확정: 고밀도 무회귀 (temporal_os 게이트) + warm-diversity 네거티브
- **warm-diversity(워커당 feedback+seed fan-out, v76)**: prob_13이 73634로 일관되나 v74(72390)
  보다 나쁨. 원인: 2개 exact_reassign에 예산 쪼개 각 CP-SAT basin 품질↓ + 4워커가 이미
  feedback/seed 다양성을 cross-worker best-of로 제공(중복). → **폐기. v74가 이미 그 다양성 보유.**
- **고밀도 prob_30-40 (v71 vs v74, 2 trial)**: 9/11 tie, prob_32 -1.2%, prob_40 +563%(변동).
  temporal_os 확인: prob_30/32/34/40/27 모두 **≥0.30 → 고밀도 경로 = v71과 바이트 동일 코드.**
  즉 prob_40 스윙은 초고밀 인스턴스 고유의 RNG 변동이지 v74 퇴행 아님(같은 코드). prob_24는
  temporal_os=0.252 → streamlined → v74가 개선(Z3-지배).
- **확정**: v74 변경은 temporal_os<0.30(저밀도/Z3-지배)에만 작용. 고밀도(Z1-지배)는 v71과 동일,
  Z1 near-optimal이라 헤드룸 없음. **v74 = 실질 최적, 추가 레버 없음.**

## ★ 세션 최종 결론 ★
- **제출 = submit_v74.zip** (7파일). 저밀도 -9.1%(prob_20 -16.6%, prob_19 -11.5%, prob_13 -4.2%),
  고밀도 무회귀. 완벽 일관.
- 배운 것: (1) use_cpp 버그가 v71의 streamlined+VLNS 경로를 통째로 죽이고 있었음(최대 발견).
  (2) 저밀도는 warm-limited(iteration도 warm-diversity도 안 통함). (3) 고밀도 Z1 near-optimal.
- 보존: cranepack.cpp(오라클+refine), vlns.py, myalgorithm_v74/v75.py, undef.py(AST 버그스캐너).

---

## v77: High-density path cleanup (myalgorithm.py 5969 -> 5187 lines, -13%)

Goal (user): the high-density path is "혼잡" (congested); strip unnecessary
things, accept 3-4% loss for clean code.

### TIER-1 — dead-code removal (byte-identical, validated zero-regression)
Removed code that never runs in production:
- `_cpsat_schedule` / `_replay_schedule` / `_try_global_schedule` + the
  `_USE_GLOBAL_CPSAT = False` block (hardcoded off) — 217 lines.
- `_repair_touch` + its call (gated on `repair_ok`, always False).
- `_smallright_construct` dead dispatch zoo: `feat_w` 12-feature scorer,
  `atc`/`stdens`/`sac`/`cpsat`/`ext_entry`/`tcp` orders — production only ever
  passes `mode` + `step` (order defaults to "rank").
- `_hybrid_construct` dead order variants (rank_a/rank_a2/area_due/rank_d/
  bigfirst/baylimit/cpsat) — production uses only rank/edd.
- `coreperi_flag` and `il_mode` dead branches (both constants False).
- BRKGA `else` fallback + PREFPOLISH legacy branch (dead at env defaults).
- Mode `bigbottom` (no caller).
- The 8 gate lambdas' overfit-fingerprint comment essays (180 lines) -> a
  concise worker-role table (50 lines), preserving the exact boolean outcomes.

Validation (v74 vs v77, 30s, 2 trials): identical on prob_21/26/31/33/35/38 and
LD guards prob_19/20/13; prob_36 within 0.09% noise; prob_40 shows the same
pre-existing timing-race variance in BOTH versions.

### TIER-2 — construction mode-zoo collapse (validated equal-or-better)
Ablation (v74, DIRS_EXTRA/BRKGA/PREFAWARE off) showed corner/BRKGA/prefaware are
NO-OPS on high-density (prob_30/35/38 identical across all settings; corner even
HURTS prob_21). So collapsed the hybrid worker's constructors to the proven set:
- Kept: flatbl, bigleft, leftbottom (primaries) + prefaware (the Z3 lever).
- Removed: corner_primary (cornerTL/BL/TR/BR), diagonal, coreperi + `parker`.

Validation (v74 vs v77, hi_ratio set): prob_27 **-3.9%** (better), prob_33 more
stable, prob_36/37/38/39/28 identical. The removed modes' "wins" (e.g. the
diagonal "prob_37 -9%" comment) were overfit noise — prob_37 is byte-identical
without them; prob_28 (the prefaware instance) is preserved.

### Known pre-existing issue (NOT introduced by cleanup)
prob_40 (n=250, large hi_ratio) has ~8-10x objective variance across trials in
BOTH v74 and v77 (1.99M vs ~17-19M) — a timing race in the bl_full worker's
step=1 completion under CPU contention. Candidate for a future robustness fix.

---

## High-density LBBD prototype (Gurobi master + cranepack/engine oracle) — hdlbbd.py

Motivation: on high-density instances the entire Z1 (tardiness) is congestion-
WAITING — measured floor Z1 (every block enters at its release) = 0 for
prob_27/38/40/37, while v77 achieves Z1 1796/2629/2751/488. And Z1 is 91-93% of
the score on prob_27/38. So there is 100% theoretical room IF a smarter schedule
can admit more blocks concurrently.

Prototype (research/exact_packer/hdlbbd.py): fix v77's bay assignment; per bay,
a Gurobi time-indexed min-sum-tardiness MASTER with a per-time AREA-cumulative
capacity (demand = true union-of-layers footprint, cap = bay area * eta);
realise the resulting entry schedule and grade.

Result on prob_38 (v77 Z1 = 2629):
- Master (area, eta=1.0) predicts Z1 = 675 (optimistic).
- Realised with COARSE cranepack (step 2): Z1 ~1891 but 783 crane violations —
  the coarse grid lets blocks overlap slightly; utils rejects it. Illusion.
- Realised with the EXACT ogc_fast engine (== utils feasibility): Z1 = **4711**,
  WORSE than v77's 2629. obj 65.6M vs 37.8M.

Diagnosis / conclusion (empirical confirmation of the area-proxy thesis):
The AREA-cumulative master OVER-PROMISES concurrency — it schedules early entries
believing blocks fit by area, but the crane descent-conflict prevents that
density, so the exact realisation slips and LOSES to v77's crane-tuned greedy.
This is exactly why the old _cpsat_schedule (also area-master) was disabled.
To win, the master's capacity must be CRANE-AWARE (cranepack), not area — i.e.
put cranepack's true max-concurrency into the master (or as feasibility cuts).
That is the remaining (larger, still-uncertain) work; the area version is a
measured negative. Also: the naive realiser positions worse than v77's
bigleft/free-span greedy, compounding the loss.

### Crane-capacity master — decisive pre-measurement (capprobe.py) = NEGATIVE
Before building a cranepack-capacity master, measured the necessary condition:
at each bay's most-congested instant on prob_38, can cranepack co-place MORE
than v77 achieved there? (If not, there is no concurrency to recover.)

prob_38 (v77 Z1 2629):
- bay0 @t=44: v77 concurrent=13, cranepack_max=15  -> ROOM +2  (but only 15% of Z1)   [6s]
- bay1 @t=43: v77=27, cranepack=26 -> NO room   (40% of Z1)   [134s]
- bay2 @t=45: v77=39, cranepack=37 -> NO room   (45% of Z1)   [111s]

Conclusion: the bays generating 85% of the tardiness (bay1, bay2) have NO
concurrency room -- v77's greedy already packs at/above cranepack's reach there.
Two further nails: (1) cranepack actually found FEWER than v77 on the dense bays
(26<27, 37<39) -- its coarse step-4 grid is WEAKER than v77's exact engine at high
density, so it cannot even supply a useful higher-capacity signal; (2) each
cranepack window took 110-134s -- computationally impossible online in a 30s budget.

Net: the schedule-first / crane-capacity-master direction does NOT pay off on
high-density. It re-confirms (now with a direct concurrency measurement) that
v77's greedy is already near the crane concurrency limit on the binding bays --
i.e. high-density Z1 is near-optimal. Cheap measurement, saved a large build.
Shipped solver unchanged (v77).

### "Gurobi done right" — grid set-packing for one packing window (gpackgrid.py)
Tested whether a PROPER Gurobi formulation (not naive big-M) can match the engine
on the fine 2D nesting subproblem: cell set-packing, y[b,o,p] with per-block <=1 and
per-cell <=1 (tight relaxation + clique cuts), union-of-layers footprint rasterised
to a grid; MIPFocus=1, Presolve=2, Symmetry=2, Cuts=2.

prob_38 bay1 window (v77 concurrent = 27):
- grid step 2: Gurobi placed 24, bound=inf (no bound in 20s), 73936 vars, solve 20s
  -> LOSES to v77 (27) and cranepack (26).

Reason (discretisation dilemma): a grid fine enough to match continuous exact
placement is too large (74k binaries at step 2 already yields no bound in 20s);
a coarser grid over-reserves boundary cells -> under-packs. Ranking on this window:
exact ogc_fast engine (27) > cranepack heuristic (26) > Gurobi grid MIP (24).

Conclusion: fine 2D irregular NESTING is a domain where specialised geometric
heuristics/engines beat a general MIP -- the MIP must discretise (killing the
continuous placement freedom the engine exploits) and the fine-grid model explodes.
Gurobi's genuine strength here is the ASSIGNMENT + SCHEDULING layers, not the
nesting. (Consistent with the earlier naive-MIP 36s result and cranepack's 60x win.)

### Gurobi scheduling with NoRel + achievable capacity (gsched2.py) — definitive negative
Gave Gurobi every fair chance at the SCHEDULING layer (not nesting): per-bay
time-indexed min-tardiness, capacity = v77's peak achieved concurrent footprint area
(demonstrably achievable, not full-bay), NoRelHeurTime on, warm-started from v77.
Then a CLEAN controlled realisation: the SAME dense packer (v71 _smallright bigleft)
run with rank order (A) vs Gurobi's schedule order (B, via ext_entry) -- isolating the
schedule lever from realiser quality.

Result (Z1, same packer):
  prob_38 (tOS .72):  A rank=2629,  Gurobi pred=2226,  B Gurobi-order=3130  -> LOSE
  prob_37 (tOS .50):  A rank= 584,  Gurobi pred= 492,  B Gurobi-order= 733  -> LOSE

The area-relaxed "gain" (-15/16%) is an ILLUSION: Gurobi optimises entry times under an
area capacity that is blind to packing density, so its "optimal" schedule is a POOR
packing dispatch order.  v77's rank order (big-first) packs densely (preserves free
span), which matters more than the schedule.  A control (realctl.py) separately showed
a naive engine realiser packs +63% worse than v77 on v77's OWN schedule -- so earlier
"realise loss" numbers were realiser noise; this test removed that confound and Gurobi
still loses.

FINAL: across capprobe (no concurrency room), gpackgrid (grid MIP loses to engine),
and gsched2 (Gurobi order loses to rank with the same packer), every angle converges:
high-density Z1 is near-optimal under v77's greedy. A general MIP cannot beat it because
the binding constraint is geometric crane-packing DENSITY, which the LP relaxations do
not capture -- and v77's greedy already co-optimises packing+schedule near the frontier.
Gurobi/NoRel work as designed; this problem's high-density regime just isn't where a
monolithic MIP wins. Ship unchanged (v77).
