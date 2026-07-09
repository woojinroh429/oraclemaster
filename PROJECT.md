# OGC 2026 — 프로젝트 기록 (전략 실험 종합)

셔야드 블록 패킹+스케줄링. 목적 = w1·Z1(지각) + w2·Z2(부하불균형) + w3·Z3(선호).
불규칙 다각형(레이어), 크레인 진입/이탈 제약, 베이×시간 2D+시간. Z1이 고밀도에서 지배.

## 핵심 구조 사실 (측정으로 확립)
1. **밀도는 3D 레이어 겹침에서 온다.** peak 혼잡시 베이내 블록 footprint가 2.3~3.8배 중첩
   (2D union은 베이의 16~32%만). 즉 2D 테셀레이션이 아니라 레이어 인터리빙이 밀도 원천.
2. **고밀도 지각은 구조적.** 대기블록 100%가 릴리즈시각 삽입불가(엔진검증). peak 34개 동시
   배치가 이미 최대밀도(재배치 강한탐색으로도 못넘음). => Z1은 순수 "입장지연".
3. **exit = entry + processing (즉시이탈).** overstay 없음. 지각=입장지연이지 체류시간 아님.
4. **밀도 이득곡선은 밀도와 뒤집힌 U.** best-of 이득: 저밀도(<0.85) 0%, 중밀도(0.85~1.15)
   평균7.6% 최대18.7%, 고밀도(>1.15) 1.2%. 중밀도가 sweet spot.
5. **저밀도(P1/P2, ratio<0.6)는 Z1=0 => Z2가 목적 지배**(Z3는 이미 ~0). 부하균형 배정이 레버.
6. ratio 게이팅(사용자확인): P1/P2<0.6, P5 0.6~0.7, P3/P4/P6>=0.7. = peak _demand_ratio 스케일.

## 실험한 전략 전부 (~25종) — rank+bigleft가 고정점
| 축 | 시도 | 결과 |
|---|---|---|
| 디스패치 순서 | EDD, ATC(S), CP-SAT, 회전율(space-time density), 희생양, 다변수(width/height/proc/work/pref) | 전부 rank(due+area) 못이김 |
| 배치 모드 | flatbl, leftbottom, diagonal, bigcorner, bigright, bigtop, coreperi, spread, **interlock(pair-packing)** | 고밀도는 bigleft 최선; 중밀도는 coreperi/bigright 승 |
| CP-SAT | order(area/width cumulative, eff스윕, 사전식), bay배정, window재패킹 | 전부 흡수/악화 |
| slack 재분배 | 대기창 여유블록 이동 | 이득 0 |
| 2D/3D nesting | sparrow(2D 논문), sparrow-3d 밀도프로브 | 2D는 레이어겹침에 부적합; 3D 헤드룸 0 |

### density-score / pair-packing (사용자 요청, 명시적 결론)
- **density-score 정렬**(면적/외접사각형, 면적/convexhull): tardiness 악화(stdens prob_38 +29%,
  example rect/hull_dens 1053->1079/1281). 큰-급 우선(rank)을 왜곡.
- **pair-packing/interlock**(bbox 겹침 최대화로 오목부에 끼우기): 고밀도 악화(prob_37 +21%,
  prob_38 +14%). 같은자리 적층이 이후삽입 막음.
- => 둘 다 이 문제엔 부적합. 이유=밀도가 3D레이어겹침에서 오지 2D 맞물림이 아님. NFP가 이미
  레이어별 오목부를 암묵 활용.

## 채택된 개선 (검증·무회귀)
1. **coreperi 전용 워커** (numba guard 교체): prob_33 obj -14.6%, A/B 6/6 무회귀.
   중밀도 winner를 dedicated 워커+best-of로 추가(교체 아님). 패치: prototype/coreperi_worker.patch.
2. **degenerate zero-area 접촉 리페어**: C++엔진이 exact-touch를 통과시켜 공식checker가 거부하는
   구성(prob_15/16/19/34)을 위반블록 재배치로 수정. 무회귀(견고성 보험).

## 수동/에이전트 배치 탐색 (사용자 요청)
- 공식 shapely geometry로 직접 배치 하네스 구축(prototype 아래 pg2.py 개념). **소형(10블록)
  에선 동작**(example edd+bigleft = baseline 1053 재현).
- **고밀도(n>=100)엔 shapely가 계산상 불가**(1전략 240s에도 미완주). 실제 알고리즘이 C++엔진
  쓰는 이유. => 고밀도 전략탐색은 빠른 엔진으로 수행(위 ~25종 스윕이 그 결과).
- 결론: 배치전략 공간은 광범위 탐색됨. **새 nesting 트릭(density/pair)은 이득 없음**, bigleft/
  rank가 near-optimal, 유일한 실이득은 중밀도 coreperi(전용워커로 채택).

## 남은 실이득 후보
- **P1/P2 저밀도 Z2 최적화**(부하균형 배정): 미탐색. 저밀도 대량 인스턴스 점수 = Z2. 헤드룸 가능.
- 중밀도 방향 best-of 확대(bigright/bigtop도 dedicated 워커화 검토).

## 상세 기록
prototype/results/ 아래: packing_density, bay_fill_verification, slack_redistribution,
window_repack, sparrow_and_density, placement_robustness_scan, placement_direction_bestof,
direction_correlation, v34_integration_reality, coreperi_worker_win 등.

## 제출본 v35 (coreperi 워커 + degenerate 리페어) vs v34 최종 A/B
| 밀도 | 예시 | v35 vs v34 |
|---|---|---|
| 저밀도 P1/P2 | prob_2 tie, prob_5 -1.4%, prob_9 tie | tie~미세개선, 무회귀 |
| 중밀도 | prob_33 | obj -14.6% |
| 고밀도 포화 | prob_37/38/40/27 | tie |
=> v35는 전 밀도에서 v34 이상(무회귀). 큰 이득은 중밀도. 제출: submit_v35.zip.
P1/P2 추가이득은 Z2 부하균형 최적화 필요(미구현).

## 전략 연구: ES(진화탐색) 정책 학습 (torch/GPU 없이, bitmask 시뮬레이터)
파라미터화 정책(dispatch 6특징 + position 5특징 가중합)을 자가구현 (μ,λ)-ES로 학습.
prob_21+25(중밀도), pop16 × 40세대 = 1248 롤아웃. sim obj 1.61M->1.06M(-34%) 수렴.
(bitmask+SX3라 절대값은 보수적; 학습된 '전략'이 연구산출.)

### 창발한 최적 정책 (ES가 스스로 발견)
- Dispatch(낮을수록 먼저): due +1.95(지배), proc +1.09, slack +1.01, area +0.98,
  width +0.54, height +0.20 => "급함(무겁게)+짧음+저slack+큼 먼저"
- Position(min): wx +1.63(좌측 지배), free-span보존 +1.43, wy +0.28(바닥),
  flat +0.19, anti-overlap +0.42 => 사실상 bigleft

### 결론
- **ES가 독립적으로 rank+bigleft를 재발견** = near-optimal 확증.
- 정제(refinement) 2가지 발견: (a) due를 area의 ~2배로 무겁게(rank는 1:1),
  (b) proc(짧음)+slack(급함) 추가(rank 미사용). => 실엔진 전이 테스트 가치.
- 한계: 1248 롤아웃 규모(100M 아님), sim 보수적. 신경망RL은 GPU 부재로 불가.
  harness: prototype/rl_strategy.py (특징/세대/인스턴스 확장 가능).

### ES 학습전략 실엔진 전이 테스트 (사용자 요청: 모든 파라미터 동시 최적배치)
ES 가중치 {due1.95,area0.98,proc1.09,wid0.54,hgt0.20,slack1.01}를 feat_w로 실엔진 bigleft에 이식:
| 인스턴스 | rank Z1 | ES-feat Z1 | 판정 |
|---|---|---|---|
| prob_25(중) | 366 | 415 (+13%) | rank |
| prob_33(중) | 981 | 1006 (+3%) | rank |
| prob_37(고) | 487 | 560 (+15%) | rank |
| prob_38(고) | 2359 | 2547 (+8%) | rank |
| prob_5(저) | obj808864 | 821515 | rank (ES Z2 8602->1195 but Z3상쇄) |
| prob_9(저) | obj1027575 | 1095810 | rank |
| prob_22(저) | obj1958140 | 1808963 (-7.6%) | ES |
=> 전이 실패(중/고밀도 rank 우세, 저밀도 mixed). 근본원인: ES가 보수적 bitmask sim(SX3)에서
   최적화 -> 실제 NFP 엔진과 보상구조 달라 정제가 안 옮겨감. 결론: ES가 rank+bigleft를
   재발견(near-optimal 확증)했으나 정제는 sim 아티팩트 = rank의 견고성 역증명.
   교훈: 학습전략 전이하려면 sim이 실엔진과 일치해야(느림). feat_w에 slack특징 추가(inert).

---

## v35 히든 회귀 진단 & v36 수정 (P5 제외 악화 원인)

### 히든 리더보드 결과 (v34 -> v35)
| | P1 | P2 | P3 | P4 | P5 | P6 |
|---|---|---|---|---|---|---|
| 방향 | ~ | +14% 악화 | +6.6% 악화 | ~ | **-9.1% 개선** | ~ |
=> P5만 개선, P2/P3 악화. "왜?"

### 원인 (v34->v35 diff를 실제로 검증)
v35가 히든 인스턴스에 미친 **유일한** 변경 = `_coreperi_for` 워커가 numba guard(마지막
워커 n-1)를 **모든 인스턴스에서** 교체한 것. (flat_bl `_hi_ratio>=0.60` 게이트는 diff에서
context 라인 = 이미 v34에 있던 것, v34->v35 변경 아님. 나머지 place_custom 신규 모드/
feat_w/order=cpsat 는 명시 인자로만 도달 -> 기본 경로 미사용.)
- P2(ratio<0.60)는 hybrid도 없음 -> coreperi가 P2를 건드린 **유일한** 변경 = 원인 확정.
- 기전: 가벼운 numba guard를 **무거운** coreperi(풀 구성+ALNS+polish)로 교체 =>
  (a) 고정 서버 CPU/시간예산에서 주력 C++ 워커 3개를 굶김(경합),
  (b) numba guard가 push-only로 도달하던 **P1/P3 우세 basin**을 best-of에서 제거.
  => P2 +14%, P3 +6.6% 악화.
- P5(0.60~0.70)는 coreperi가 도달한 **유일한** v35 변경 => coreperi = P5 개선(-9.1%) 동인.
결론: coreperi는 **P5에서 순이득, P2/P3에서 순손실**. 밴드별로 정반대.

### v36 수정 (외과적)
1. `_coreperi_for(i)`: `_p5_band = (0.60 <= ratio < 0.70)` 일 때만 켠다.
   - P1/P2/P3/P4/P6 -> numba guard 복원 = **v34 동작/점수 그대로** (회귀 제거).
   - P5 -> coreperi 유지 = **개선(-9.1%) 유지**.
   - 상한 `<0.70` 타이트: P3(>=0.70)를 잡으면 검증된 회귀 / 경계 P5를 놓치면 그냥 v34(무해)
     => 비대칭 리스크라 상한을 조인다.
2. `_repair_touch`도 `repair_ok=_p5_band`로 게이트(args 16번째 원소로 전달).
   - P3/P4/P6의 hybrid 워커(n-2,n-3)가 infeasible 구성에서 최대 15s repair로 ALNS를
     굶는 잠재 경로를 차단 -> 비-P5는 **정확히 v34**로 복귀 보장.
   - P5는 모든 워커에서 repair 유지(prob_15/16/19/34 degeneracy 이득 보존).

### 검증
- syntax OK, python3.12에서 import OK (HAVE_CPP=HAVE_OGC_FAST=True, 엔진 로드).
- args 튜플 arity 일관(16-tuple 생성=언팩), 호출부 단일(pool.map).
- 인스턴스 JSON이 이 컨테이너에 없어 end-to-end feasibility는 미실행(구조검증으로 갈음).
- 정직한 한계: 리더보드 6점 fit(밴드 경계는 학습 인스턴스 ratio 관측치 0.60/0.73 gap 기반).
  일반화 미보장. 무위험 대안 = v34(coreperi 자체 미탑재). v36 = "v34 + P5 이득만".

---

## 실엔진 ES 로컬 재현 (Colab 대신 컨테이너 4코어, torch 없이 numpy) — 2026-07-09

사용자 요청(폰이라 직접 못 돌림)으로 실엔진 ES를 이 컨테이너에서 직접 실행.
prototype/es_run/{es_np.py(학습), validate.py, one.py(1프로세스=1구성 클린평가)}.
정책=신경망 잔차 on rank: priority = rank_base(due+area) + 0.5*MLP(BF). fitness=실엔진
_smallright_construct(ext_entry, tiebreak=due) 공식 objective. 대상 prob_25(n=100,ratio1.285,지각지배).

### 학습 로그 (겉보기)
gen0 313969 -> gen12 299160 (native rank 318659 대비 -6.1%). "개선되는 것처럼" 보임.

### ★ 클린 검증에서 뒤집힘 (1프로세스=1구성, 실 알고리즘과 동일)
| inst | rank obj | ES obj | 승자 |
|---|---|---|---|
| prob_25(학습) | 318659 | **344780** | rank (ES -8.2%) |
| prob_21 | 1463033 | 1511665 | rank |
| prob_23 | 3174429 | **2922621** | ES (-7.9%, 우연) |
| prob_24(P5) | 1246567 | 1272234 | rank |
- **학습한 prob_25에서조차 ES가 rank에 패배**. ES obj=344780 = ext_entry-rank 베이스라인과
  정확히 동일 -> 학습된 잔차가 순서를 실질적으로 못 바꿈. 학습 중 -6% 는 허상.
- 클린평가는 완전 결정론적(native rank 6/6=318659, ES 2/2 재현). native rank 단독도 결정론적.

### 근본원인 = 측정 무효 (중요한 방법론 교훈)
학습 fitness가 **wall-clock DEADLINE(15s) 구성**인데 ES를 **4-way 병렬**로 평가 ->
구성이 CPU 경합에 따라 15s 안에 도달하는 내부상태가 달라짐 -> obj가 load-dependent 노이즈.
ES가 그 노이즈(운 좋은 낮은 draw)를 착취 -> best_theta는 노이즈에 과적합 -> 클린 재평가에서 소멸.
=> **wall-clock 한정 constructor를 병렬 ES fitness로 쓰면 안 됨.** fitness는 결정론적이어야
   (고정 step-count/iteration, wall-clock 아님). prob_23 승리는 학습 안 한 인스턴스의 우연.

### 결론 (재확증)
rank+bigleft 가 near-optimal. 실엔진 ES로도 rank를 신뢰성 있게/일반화되게 못 이김.
(예전 bitmask-sim ES 결론과 동일 지점을, 이번엔 실엔진 + 클린 프로토콜로 재확증.)
제대로 더 밀려면: 결정론적 fitness(step 고정) + 다수 인스턴스 동시학습 + held-out 무회귀 게이트.
단 prob_25 클린결과(ES=ext-rank, 순서이득 0)로 볼 때 천장은 낮을 것으로 예상.

---

## 시간창 Ruin + CP-SAT exact Recreate 프로토타입 (고밀도) — 2026-07-09

사용자 요청("친구가 R&R 씀"). 우리 ALNS가 이미 R&R이지만, 미개척 변형인
**시간창 ruin + CP-SAT(windowed) exact recreate**를 실제로 구현/검증. prototype/rr/rr.py.
절차: baseline(rank+bigleft) -> 지각밀도 피크 중심 |W|제한 시간창 -> 창밖 F고정 +
창 W만 CP-SAT로 재스케줄(F=배경 area수요) -> 엔진으로 잔여공간 realize -> check_feasibility.
클린(1프로세스=1인스턴스), best-of라 무회귀.

### 결과 (prob_25 창크기 스윕, baseline Z1=366)
| |W| | control(greedy recreate) | CP-SAT recreate | baseline |
|---|---|---|---|
| 12 | 382 | 378 | 366 |
| 20 | 495 | 473 | 366 |
| 29 | 531 | 493 | 366 |
다른 인스턴스: prob_21(0.78) 51->control92->cpsat123, prob_23(0.86) 193->225->239.

### 판정 — 두 가지가 동시에 참
1. **CP-SAT recreate는 greedy recreate를 일관되게 이김**(378<382,473<495,493<531).
   => "창 안 협응(coordination)" 가설 자체는 유효. 아이디어가 틀린 건 아님.
2. **그러나 둘 다 baseline에 짐.** ruin&recreate '분해' 자체가 순손실.
   창밖 70~90%를 얼리고 창을 잔여공간에 재배치하는 것이, bigleft의 '한 번의 전역 패스'보다
   본질적으로 나쁨(고정 handicap: |W|작을수록↓ 이지만 크로스오버 없음 — 최소 +3.3%).

### 근본원인 (왜 R&R이 여기선 약한가)
- **2D 패킹은 라우팅처럼 분해가 안 됨.** VRP에선 고객 빼고 재삽입이 국소비용이라 R&R 지배적.
  여기선 얼린 블록이 물리적 공간을 점유 -> 재배치 블록은 남은 자리로 밀림 -> 더 늦게 -> 지각↑.
- **CP-SAT area-cumulative가 부적합.** 실제 밀도는 크로스레이어 interleaving(다른 층 겹침 허용)에서
  나오는데 area모델은 이를 표현 못 함 -> 과포화 인스턴스에서 eff<=0.72 infeasible(0.9~1.8로 완화해야).

### 함의
이게 "고밀도에서 ALNS가 거의 개선 못 하는" 이유의 구체적 증거: 밀집 패킹에서 어떤 freeze&repair도
큰 분해 handicap을 문다. => 천장은 construction 품질이고 bigleft가 그 근처. R&R-exact-recreate
경로로도 rank+bigleft near-optimal 재확인. **통합 가치 없음(무이득). best-of라 무회귀는 보장.**
