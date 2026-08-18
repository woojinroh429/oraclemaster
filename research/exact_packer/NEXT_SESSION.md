# 다음 세션 착수 문서 — Exact Crane Packer (C++)  ★START HERE★

목표: 경쟁자(P3=81000, P4=3.1M; 우리 v71=102625/3.86M, ~20% 뒤짐)를 추월.
근거: 20% 갭 = **혼잡 베이 패킹 밀도**. 우리 greedy가 혼잡 clique에 적게 넣음(7),
exact가 많이 넣음(10, +43%). 더 넣음 → 스필↓ → Z3↓(P3) & Z1↓(P4). 양 레짐 공통.

## ★ 확정된 설계 (파인만식 검증 완료 — 이대로 가면 됨) ★

**타깃 = coarse-grid set-packing 을 C++로 빠르게.** (EP/fine/NFP-MIP 아님 — 아래 "죽은 길" 참고)

파이프라인 (각 저밀도 베이의 binding clique마다 LNS):
```
1. 혼잡 프로파일 → peak clique 추출  (congestion.py: 블록 present at peak instant, 5~18개)
2. coarse-grid 컬럼 생성 (step~6, ~1400개/clique)  c=(block, x, y, orient), entry=release(저밀도 Z1=0)
3. 쌍별 충돌 (crane j>=k 규칙, VALIDATED)  -> conflict graph
4. set-packing 풀기: max Σ placed_b   s.t. Σ_{c in b} y_c <= placed_b<=1 ;  conflict pairs y_c+y_c'<=1
   - greedy warm-start (st_best 결과를 MIP start; exact 모델에서 feasible)
   - MIPFocus=1 (좋은 해 빨리)
5. exact grader-verify (드문 raster false-neg 방지) → 위반쌍 pairwise cut 추가 → 재solve (1~2 round)
6. 넣은 블록들을 배정에 반영 → 스필 줄어듦 → Z3↓
```

## ★ C++로 옮길 것 (스코프) ★
**병목 = solve 시간 (파이썬 Gurobi step6 ~4-25s/clique, 너무 느림). 목표 clique당 ~1s.**
선택지 (우선순위):
1. **Gurobi C API** 로 set-packing 풀기 (모델은 동일, C에서 빌드+solve → 파이썬 오버헤드 제거).
   - 충돌 계산도 C++ (아래 conflict 규칙 그대로 포팅). numba conflict(0.48us/쌍) → C++ 더 빠름.
2. 또는 **커스텀 branch-and-bound** (max independent-set on conflict graph, greedy 하한 + clique bound).
   - conflict graph는 sparse(footprint 근처만) → B&B 잘 먹힐 수 있음.
3. 빌드법: st3dtcs 처럼 pybind11.
   `g++ -O3 -shared -std=c++17 -fPIC -march=x86-64-v2 $(python3.12 -m pybind11 --includes) SRC.cpp -o MOD.cpython-312-x86_64-linux-gnu.so`
   (scratchpad/build_st3/ 에 예시. 충돌+solve를 C++ 모듈로, 파이썬은 clique 추출+오케스트레이션만.)

## ★ 충돌 규칙 (C++ 포팅용, VALIDATED — conflictgen.py/fastconf.py) ★
두 배치 (블록 A@(xA,yA,oA,enA,exA), B@...): 충돌 iff **시간 공존**(enA<exB and enB<exA) AND:
- 안착: A레이어 k vs B레이어 k 겹침 (모든 k)  [resting j==k]
- A가 나중진입(enA>=enB) 또는 A가 먼저퇴장(exA<=exB): A_k vs B_j 겹침 (모든 j>k)  [A가 B 통과]
- B가 나중진입(enB>=enA) 또는 B가 먼저퇴장(exB<=exA): B_k vs A_j 겹침 (모든 j>k)  [B가 A 통과]
- 겹침 = 레이어 다각형 교차 area>0. **좌표는 Block.layers_at_pos() (world) — resolved_layers()(원점) 아님!! (이 버그로 반나절 날림)**
- 레이어수 다르면 j는 min(K)까지만 유효 (없는 레이어는 스킵).
검증: fastconf.conflict 가 grader_conflict(check_collisions+check_entry+check_exit)와 prob_20/17 0-mismatch.

## ★ 죽은 길 (다시 시도하지 말 것) ★
- **fine grid (step<=3)**: 컬럼 5k~10k → 21M 쌍 → conf/solve 둘 다 불가 (numba도 FFT마스크도 못 이김). 병목은 충돌속도 아니라 컬럼수.
- **extreme-point 컬럼**: x접촉×y접촉 곱 = ~37000 컬럼. 8방향×n블록 곱이 커서 안 줄어듦.
- **NFP-MIP (compact 연속 x,y)**: 이론상 맞지만 불규칙 nesting NP-hard, ~17조각이 solvability 경계. 큰 하드 MIP.
- **area-LBBD / column-generation**: area 용량이 크레인 feasibility를 표현 못 함 (cf=0.70도 infeasible). 근본적으로 약한 토대.
- **FFT conflict mask**: 정확(1.1% false-neg, cut로 처리)하나 컬럼수 벽 못 넘음 (21M 쌍 파이썬 iterate 73s).

## ★ 작동 확인된 참조 결과 ★
- gpack6.py (step6, warm-start, MIPFocus=1): prob_20 bay1 clique17 → **Gurobi=10 vs greedy=7 (+3)**, conf14s+solve4~25s.
- gpack2.py (step6 pairwise shapely): 동일 10 (75s) — 최초 개념증명.
- 즉 **coarse 전역최적화가 fine greedy를 이김이 재현됨.**

## ★ 파일 지도 (research/exact_packer/) ★
- congestion.py   : 혼잡 프로파일 + peak clique 추출 (interval graph)
- conflictgen.py  : grader_conflict (원시함수 조합, ground truth) + world_layers 버그수정
- fastconf.py     : numba 고속 정확 충돌 (0.48us, 0-mismatch prob_20/17)  ← C++ 포팅 기준
- raster.py       : 안전 래스터화 (보수적 팽창, false-neg 0)
- fftmask.py      : FFT 충돌마스크 (죽은길이지만 수학 참고용)
- gmaster.py      : Gurobi 배정 master (min w2Z2+w3Z3, CP-SAT와 검증일치)
- oracle.py       : 크레인 feasibility 오라클 + 조합 core
- lbbd.py         : area-LBBD (죽은길)
- gpack2..6.py    : 패커 반복 (gpack6 = 현 참조)
- ep_verify.py    : extreme-point 검증 (죽은길 확인)

## ★ 통합 시 주의 (파이프라인) ★
- 저밀도(Z1=0) 전용. 고밀도는 Z1도 있어 entry 가변 → t를 이벤트기반 후보로 확장 필요.
- 패커는 v71의 z3_relocate 자리(더 강한 버전)에 LNS 오퍼레이터로. best-of 워커라 never-worse 유지.
- v71이 현 제출 최선 (P3=102625). 패커 win 검증 전까지 v71 유지.
- 전체 A/B: prob_13/17/19/20 중앙값, 89271(prob_20 floor) 대비.

## ★ 추가 발견: coarse-to-fine 불필요, step6이 천장 (ctf.py) ★
실험: step6 전역해(10) → fine ±5 재배치(step1) → **여전히 10, 개선 없음**.
이유: bay1은 면적상 258% 과포화 → **10이 물리적 천장**이고 coarse-6이 이미 잡음.
결론:
- **C++ 목표 단순화 = "step6 set-packing을 빠르게" 하나면 됨.** 해상도 더 안 올려도 됨.
- coarse-to-fine 기계 안 만들어도 됨 (덜 과포화된 clique엔 보너스로 도울 수 있으나 필수 아님).
- 여전히 파이썬은 clique당 ~65s (conf 14s + solve 15s + overhead) → C++로 ~1s 목표.

## ★ 최종 C++ 스코프 (다음 세션 이것만 하면 됨) ★
1. 입력: clique 블록 리스트 + 각 블록의 shape/layers/release/proc/prefs, 베이 W,H.
2. coarse step-6 컬럼 생성 (C++).
3. 쌍별 충돌 (위 j>=k 규칙, C++; fastconf.py 로직 그대로).
4. set-packing max independent-set 풀기:
   - 옵션A: Gurobi C API (모델 = gpack6과 동일). 가장 확실.
   - 옵션B: 커스텀 B&B (greedy 하한 warm-start + clique bound). 의존성 없음.
5. greedy(st_best) warm-start.
6. 반환: 배치 리스트 (block, x, y, orient). 파이썬이 exact-verify 후 배정 반영.
목표: prob_20 bay1 clique17에서 greedy=7 대비 10을 ~1초에.
그다음: 모든 저밀도 베이의 binding clique들에 적용(LNS) → 전체 A/B (prob_13/17/19/20 중앙값, 89271 대비) → 이기면 v72로 통합.
