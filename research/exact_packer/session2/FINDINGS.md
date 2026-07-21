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
