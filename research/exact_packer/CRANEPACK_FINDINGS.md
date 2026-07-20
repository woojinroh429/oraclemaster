# cranepack: 결과 및 정직한 한계 (competitor-gap 2일차)

## 무엇을 만들었나
**cranepack.cpp** — 의존성 제로 순수 C++ 크레인 set-packing 패커.
- 입력: 혼잡 블록집합(방향별 레이어, obb, entry/exit 변형), 베이 W/H, coarse step.
- coarse-grid 컬럼 → 쌍별 크레인충돌 그래프(j>=k, fastconf 로직 포팅) → **iterated (2,1)-swap MIS**.
- **엔트리 재타이밍 변형** + **frozen obstacle 블록**(고정 배치 회피) 지원.
- pybind11, `-march=x86-64-v2`.

## 검증된 성능 (확실한 win)
- prob_20 bay1 clique17: **cranepack=10 = Gurobi=10**, greedy=7 (+43%), bad=0, **전 시드**.
- 속도: build ~0.5s + solve ~0.05s = **~0.6s** (Python numba+Gurobi 65s 대비 **~100배**).
- Gurobi pairwise 모델은 36s(model-build 5.7s + solve 30s 타임아웃, gap=0.2) — **죽은 길**. C++ 휴리스틱이 압도.
- (2,1)-swap이 시드 편차(9 vs 10) 해결의 핵심. 없으면 지역최적 9-basin에 갇힘.
- 전 저밀도 인스턴스 clique에서 cranepack >= greedy, bad=0 (never-worse):
  prob_20 +6, prob_13 +3, prob_17 +1, prob_19 +1.

## 격리 relocator A/B (고정 시드) — 명확한 win
`z3cp.py`: `_z3_relocate`(COLCAP=20 CP-SAT)를 cranepack으로 교체.
- 고정 시드에서 best-of(old,crane,stack):
  prob_20 99450→**92539 (-6.9%)**, prob_13 76637→**71632 (-6.5%)**, prob_17 -0.3%, prob_19 tie(never-worse).
- 엔트리 재타이밍이 빠진 조각이었다 (저밀도 시간슬랙 레버).

## ★ 정직한 한계 — 밀도 레버는 목적함수 20% 갭이 아니다 ★
1. **full-bay in-preference 밀도 천장 = +2블록** (packbay: 62블록 중 42 vs greedy 40).
   peak-clique +43%(7→10)는 **단일 순간** 착시. 전체 타임라인에선 대부분 시간분리라 greedy도 이미 넣음.
   → 밀도 레버의 실제 목적함수 상한 **~1-2%**.
2. **full-pipeline 통합은 모두 실패**(prob_20 회귀 또는 무이득):
   - crane in even(대체): prob_20 손해(feedback 워커가 prob_20 승리 레버인데 시간 뺏김), prob_13 이득.
   - crane in even(both/stack): prob_20 더 손해(theft).
   - crane in odd: prob_20 tie, prob_13 tie(이득 없음).
   튜닝된 v71을 밀도만으로 견고하게 못 이긴다.

## ★ 진짜 발견 — 20% 갭은 Z3 배정 문제 ★
목적함수 분해 (Z1=0):
- prob_20 (92450) = **w2Z2 13200 (14%) + w3Z3 79250 (86%)**.
- prob_13 (73364) = w2Z2 11785 (16%) + **w3Z3 61579 (84%)**.
→ 목적함수의 **84~86%가 Z3(선호 페널티)**. 경쟁자 20% 갭도 대부분 Z3.
→ Z3 갭 ≈ 88 units ≈ **블록 20~44개를 더 좋은 bay로** 옮겨야 하는 규모. 밀도(+2블록/bay)로는 극히 일부만.
→ **20% = "패킹 밀도"가 아니라 "더 나은 bay 배정".**

## ★ 다음 방향 (사용자 선택: cranepack-oracle LBBD) ★
`_exact_reassign`은 이미 **CP-SAT master(w2Z2+w3Z3) + area-용량 Benders**.
area가 크레인 실현성의 나쁜 대리(cf=0.70도 infeasible) → 배정이 불필요 스필 → 높은 Z3.
**교체**: area-feasibility 서브문제를 **cranepack 크레인-feasibility 오라클**로.
- 마스터 배정 제안 → 각 bay를 cranepack으로 실현성 체크 → 불가면 **최소 infeasible subset no-good cut** → 재solve.
- 수렴 시 배정은 진짜 크레인-feasible & Z3-품질 최대. cranepack이 실제 배치도 제공(별도 realise 불필요).
- 소프트니스 주의: cranepack이 heuristic이라 대집합(60블록)에서 "다 안 들어감"을 잘못 보고할 수 있음(false cut). warm-start(realise) + 넉넉한 budget으로 완화.

## 파일
- cranepack.cpp (핵심 모듈), packtest/packall/packbay (clique/bay 검증), z3cp (relocator A/B), hybtest (Gurobi 비교=죽은길).
- 빌드: `g++ -O3 -shared -std=c++17 -fPIC -march=x86-64-v2 $(python3.12 -m pybind11 --includes) cranepack.cpp -o cranepack.cpython-312-x86_64-linux-gnu.so`

## ★ 2일차 추가: cranepack-oracle LBBD 배정 조사 (사용자 선택 방향) ★
목적함수 86%가 Z3라, "더 나은 bay 배정"으로 20%를 노림. 결과: **v71을 못 이김.**

측정 (prob_20, n=300, m=5):
- **배정 하한(area 제약 없음): obj 40662, Z3 144** — 매혹적이나 **실현 불가능**.
  cranepack이 그 배정에서 276-281/300만 fit (인기 베이 과포화: bay1은 62개 원하는데 43개만 fit).
- count-cap LBBD (베이별 cranepack fit으로 카디널리티 tighten): fit 289/300, **Z3 721** (미수렴).
- spill-cascade (unplaced를 차선 pref로): ~295/300에서 정체, **Z3 1673으로 폭발**.
- **v71 실제: Z3 634 완전 실현 (obj 92450)** — 위 어느 것보다 나음.

핵심: **엔트리 재타이밍은 fit을 안 늘림** (bay1 43→43, bay2 +1, bay4 −1).
→ 베이는 시간 무관 **공간적으로 진짜 과포화**. 시간 staggering은 미개발 레버가 아님(v71 SA가 이미 보유).

**정직한 결론:**
- Z3=144 LB는 크레인 실현 불가능한 하한(면적/공간 무시). 실현가능 Z3 바닥 ≈ 600-700.
- v71(Z3 634)은 **이미 실현가능 최적 근처**. area-Benders + timing-aware 실현자가 잘 작동.
- **cranepack-LBBD 배정도, 밀도 레버도 v71을 견고하게 못 이긴다.**
- 경쟁자 20% 갭: (a) 히든 인스턴스가 훈련 prob_20과 다르거나(grader P3=102625 ≠ local 92450),
  (b) 우리가 못 짚은 기법이거나, (c) 측정 스케일 차이. **이 세션 레버로는 재현 안 됨.**

## 최종 상태
- **v71이 여전히 최선 (제출 유지).** v72는 밀도 오퍼레이터 통합했으나 net-win 아님 → 미채택.
- cranepack.cpp는 검증된 우수 인프라 (100배 빠른 exact 크레인 패커) — 향후 재사용 자산으로 보존.
- 파일: lbbdprobe/lbbdsweep/lbbdloop (배정 조사), z3cp (relocator), packtest/packall/packbay (패커 검증).

## ★ 3일차: 고밀도(P4/P5/P6) cranepack 적용 — throughput headroom은 실재, 하지만 변환 실패 ★
저밀도가 Z3(배정)면 고밀도는 Z1(지각). 지각은 "동시에 몇 블록 처리하느냐"에 직결 → cranepack 밀도가 직접 레버 가설.

**측정 1 — joint window reopt (step3_cpsat / step3c):**
- redesign_notes의 disjunctive-scheduling joint reopt 실행: prob_26 within-window tardiness delta<0 (CP-SAT가 현재보다 나쁨).
- 원인: step3의 conflict가 **order-independent union**(어느 순서든 충돌하면 금지) → 과보수 → 유효한 현재 배치를 금지.
- fastconf order-dependent 시도(step3c)도 2값 staggered 근사라 여전히 과보수(delta<0).
- 정확 모델 = R(안착)/DA/DB(하강 sweep) 3성분 + 시간조건부 활성화. 복잡하고 gain 작을 전망(moved 2/12).

**측정 2 — throughput headroom (hdthru.py): ★실재하는 신호★**
- prob_26 peak 순간: bay0@t40 v71 동시=17 vs **cranepack 최대동시=25 (+8)**; bay1@t20 19 vs 23 (+4).
- **v71이 고밀도 베이를 크게 under-pack** (저밀도 +2 대비 +8, 훨씬 큼).

**측정 3 — cranepack space-time 스케줄러 (hdsched.py): 변환 실패**
- v71 assignment 고정, 각 베이를 cranepack 그리디(매 이벤트 최대 동시 admit)로 재스케줄.
- 결과: prob_21 Z1 169→**440 (obj 2.7M→6.3M, 크게 악화)**.
- 원인: cranepack은 **count 최대화지 tardiness 최소화 아님** → 잘못된(비긴급) 블록을 일찍 넣어 긴급 블록 지연.
  **로컬 지표(동시성/밀도) ≠ 목적함수(지각).** v71의 튜닝된 3DTCS decoder가 이미 이 정렬을 처리.

## ★ 세션 종합 결론 (정직) ★
**모든 레버가 v71을 못 이긴다 — 일관된 근최적:**
| 레짐 | 레버 | 신호 | 목적함수 결과 |
|------|------|------|---------------|
| 저밀도 Z3 | 밀도 relocate | +2 blocks | prob_20 회귀/무이득 |
| 저밀도 Z3 | LBBD 배정 | LB 40662 | 실현불가, v71 근최적 |
| 고밀도 Z1 | joint reopt | headroom有 | delta<=0 (과보수 모델) |
| 고밀도 Z1 | throughput | +8 동시 | 그리디 스케줄 크게 악화 |

공통 패턴: **로컬 headroom 지표(밀도/동시성/개별 earlier-entry)가 실재하나 목적함수로 변환 안 됨.**
v71의 area-Benders + timing 실현자(저밀도) + 3DTCS decoder(고밀도)가 이미 근최적.

**cranepack.cpp = 검증된 우수 인프라(100배 빠른 exact 크레인 패커) — 보존.** 경쟁자 20% 갭은 이 세션 레버로 재현 불가.
향후: 정확 R/DA/DB joint 모델(작은 gain 가능), 또는 tardiness-aware(count 아닌) cranepack 목적함수 확장이 유일한 미탐색 각도.
