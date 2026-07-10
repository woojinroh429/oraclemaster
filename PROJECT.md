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

---

## Regret recreate 실험 (사용자: 추가 연산자로 중밀도 이득) — 2026-07-09

### 코드 변경 (엔진, 무회귀)
- `_try_place_block(..., commit=True)`: commit=False면 상태에 add 안 하고 best만 반환(평가용).
- `_alns(..., recreate="greedy")`: recreate="regret"이면 고정순서 대신 매 스텝 regret-2
  (베이별 차선-최선 tardiness 최대 블록부터) 삽입. 기본값 greedy라 기존 동작 불변.
- prototype: rr/rr.py(one-shot recreate 비교), rr/ab_alns.py(ALNS내 greedy vs regret),
  rr/iter_lns.py(반복 window-LNS+regret).

### 발견 1 — one-shot recreate: regret >> greedy (창 프레임)
창밖 고정 + 창(20~29블록) 재배치: regret이 greedy control을 항상 이김. baseline은
가끔 이김(prob_25@창20 -0.5%, prob_23 -2.3%) but 창크기/인스턴스 의존적(fragile).

### 발견 2 — drop-in regret in ALNS: 이득 0
_alns의 greedy를 regret으로 교체(작은 14블록 제거 유지): prob_23/25 둘 다 greedy=regret=
baseline (개선 0). 이유: baseline이 ALNS 이웃(작은제거)의 국소최적. 발견1 이득은 '큰 창을
통째 destroy + joint regret'라는 다른 이웃에서 나온 것 -> ALNS가 그 move를 안 함.

### 발견 3 ★ — 반복 window-LNS + regret: 실이득 (무회귀)
{지각 시간창(약22블록) ruin -> regret recreate -> 개선시만 채택} 반복. accept-only라 절대 무회귀.
| inst | ratio | 이득 | accepts | 출처 |
|---|---|---|---|---|
| prob_23 | 0.859 | +2.34% | 1 | Z1(193->191) |
| prob_25 | 1.285 | +2.29% | 6 | Z1(366->348) |
| prob_24 | 0.602(P5) | **+13.94%** | 4 | Z2/Z3(obj 1.25M->1.07M) |
| prob_21 | 0.779 | 0 | 0 | 보호(저지각) |
| prob_28 | 0.878 | 0 | 0 | 보호 |
| prob_30 | 0.903 | 0 | 0 | 보호 |
핵심: 승리 재료 = 큰 tardy-window destroy + joint regret recreate + accept-only 반복.
prob_24(+14%)는 히든에서 중요한 P5 밴드. n큰 인스턴스는 반복수 적어(느림) 이득 작음/구성bound.

### 다음 (통합 계획)
가장 안전: pool 종료 후 best-of 승자에 window-LNS를 '남은 시간'만큼 refinement로 실행
(accept-only + 이미 pool 끝나 경합 없음 = coreperi식 starvation 위험 없음). n/시간 게이트.
반드시 full A/B(v36 vs v36+refine, 인스턴스당 1프로세스, 무회귀)로 순이득 확인 후 채택.

### 발견 4 ★★ — full solver A/B: window-LNS refinement은 순손실 (이득 허상이었음)
window-LNS를 실 solver에 통합(pool 종료후 남는시간 25% 예약 + accept-only refinement,
n<=160 게이트, env WLNS_REFINE). 실 algorithm() OFF vs ON, 인스턴스당 1프로세스, tl=45:
| inst | ratio | OFF obj | ON obj | 판정 |
|---|---|---|---|---|
| prob_21 | 0.779 | 1394173 | 1405243 | ON 악화 +0.8% |
| prob_22 | 0.525 | 1009408 | 1035047 | ON 악화 +2.5% |
| prob_23 | 0.859 | 2822633 | 2822633 | tie |
| prob_24 | 0.602 | 970289 | 970289 | tie |
| prob_25 | 1.285 | 282173 | 284137 | ON 악화 +0.7% |
=> **모든 인스턴스 ON<=OFF. 순손실.** 어떤 인스턴스도 이득 없음.

### 근본원인 (내 측정 실수 — 세 번째 같은 함정)
발견3의 window-LNS "이득"은 **baseline-only 구성(rank+bigleft 단일패스)** 대비였음.
그런데 **실 solver의 병렬 ALNS가 이미 훨씬 더 낮춤**: prob_25 baseline-only 318659,
window-LNS 311351, **실solver 282173**(훨씬 좋음). prob_23도 baseline 3174429 ->
window-LNS 3100069 -> **실solver 2822633**. prob_24 1246567 -> 1072796 -> **970289**.
=> refinement를 실 solver 출력(이미 강함)에 얹으면 **개선할 게 없음**(tie), 예약한 시간만 손해(악화).
교훈: **항상 full solver 출력에 A/B 하라. 약한 baseline 대비는 허상 이득을 만든다.**
(coreperi=로컬중밀도 이득->히든회귀, ES=경합노이즈 이득->클린손실, window-LNS=약baseline 이득->
 full손실 — 전부 '잘못된/약한 기준 대비 측정'이 근본원인. 동일 실수 3회.)

### 조치
통합 전량 revert -> sv34/myalgorithm.py == v36 (md5 69608284..., byte-identical). 제출은 v36 유지.
prototype/rr/{rr,ab_alns,iter_lns,ab_full}.py 는 기록용 보존. regret recreate 자체는
greedy를 이기지만(발견1), 실 ALNS가 이미 그 이득을 취해서 추가 가치 없음.

---

## 전 방향(8-direction) 연구 & full-solver 비교 (사용자 요청) — 2026-07-09

### 8방향 (flatness h primary + directional secondary)
wall: bigleft, bigright, bigbottom, bigtop / corner: cornerBL, cornerBR, cornerTL, cornerTR.
기존 v36엔 bigleft/right/top/bottom(flatbl)/BL(diagonal)만 -> cornerBR/TL/TR 신규 추가(연구용 copy).
prototype/dirs_modes.txt(코드), dsweep.py(구성스윕), abdir.py(seed->ALNS), ab_full(풀솔버 A/B).

### construction 스윕 (Z1, 순서=rank 고정) — 신규 corner가 중밀도서 자주 승
| inst | ratio | bigleft | 승자 | 이득 |
|---|---|---|---|---|
| prob_25 | 1.285 | 366 | cornerTL 314 | -14% |
| prob_26 | 1.000 | 605 | cornerTR 486 | -20% |
| prob_28 | 0.878 | 87 | cornerBL 74 | -15% |
| prob_30 | 0.903 | 208 | cornerTL 187 | -10% |
| prob_24 | 0.602 | 9 | bigright 0 | Z1->0 |
| prob_21/22/23 | 저~중 | 승 | (bigleft/bigbottom) | 0 |
=> 방향승자는 혼돈적(인스턴스별), 신규 cornerTL/TR/BL이 prior 4-mode가 놓친 중밀도 승 다수.
abdir(prob_25): cornerTL seed 272465 ->ALNS 272465 (ALNS 정체) -> bigleft 318659 대비 -14.5% 생존.
=> 고립/구성단계선 방향이 진짜 이득 (window-LNS와 달리 ALNS가 못 지워서 생존).

### ★ full-solver A/B (실 algorithm(), DIRS off=v36 vs on=+8방향 tail best-of) — 전부 tie
prob_21/23/25/26/28/38 전부 OFF==ON. prob_24만 ON<OFF(-2.4%)이나 pool-timing 노이즈
(OFF가 run마다 970289<->993419 변동). => **통합 순이득 0, 무회귀.**

### 왜 고립이득이 full-solver서 안 잡히나
1. tail-변이로 추가하면 hybrid 워커의 tail 예산이 rank+edd×(flatbl/diag/leftbottom/bigleft)로
   이미 소진 -> 신규 방향이 step=1 품질 attempt를 못 받음 -> 272465 재현 못 함(284137 tie).
2. 잡으려면 방향마다 전용 워커(coreperi식) 필요 -> 4코어서 오버구독/경합 = coreperi 교훈(히든회귀).
3. pool-timing 노이즈(~2%)라 작은 효과는 반복측정 없이 분해 불가.

### 결론 (4번째 같은 패턴)
방향은 고립선 진짜 이득(중밀도 -10~-20% 구성)이나, 현 아키텍처(4코어, tail best-of)가 못 잡음.
ES/R&R/window-LNS/directions 모두 "고립이득 -> full-solver서 tie/손실". 근본: full-solver가
이미 강하고 4코어 예산이 추가 다양성을 감당 못 함. v36 유지. dirs/는 연구용(미배포).
미시도: adaptive-primary(방향을 싸게 probe->승자를 워커 PRIMARY로, tail 아님) = 유일한 미개척 통합.

---

## ★★★ v37: corner-primary — 세션 첫 실이득 (full-solver 검증, 무회귀 게이트)

### 사용자 요청: corner 방향 종합 측정
corner-best-of(cornerTL/BL/TR/BR) 구성이 bigleft 구성을 종합적으로 이김(6/9, obj +8~18%).

### 통합 (dirs/ 연구 -> v37)
- place_custom에 cornerBR/TL/TR 신규 모드 추가(cornerBL/bigbottom 포함 8방향 완성).
- 홀수 hybrid 워커의 PRIMARY를 corner-best-of로: 4코너 각각 step=1 구성 -> best 채택.
  ★핵심 버그수정: step=2 probe가 코너를 오정렬(step2승자!=step1승자, prob_25서 cornerTR
   뽑고 272465 놓침) -> 4코너 모두 step=1로 평가해야 진짜 승자(cornerTL) 잡음.
- 게이트 n<=160: 대형(n=250)은 4x step1이 못끝나 굶고 bigleft 워커 잃어 회귀
  (prob_38 -2.5%) -> n<=160으로 제한하면 회귀 사라짐.

### full-solver A/B (실 algorithm(), v36 vs v37, 인스턴스당 1프로세스, 2회 재현확인)
| inst | ratio | n | Δobj |
|---|---|---|---|
| prob_21 | 0.779 | 100 | **+4.96%** |
| prob_24 | 0.602(P5) | 100 | **+3.86%** |
| prob_25 | 1.285 | 100 | **+5.50%** (2회 동일) |
| prob_28 | 0.878 | 150 | **+3.61%** (2회 동일) |
| prob_22/26 | | | tie |
| prob_23/30 | | | -0.36/-0.64% (pool노이즈 ~2% 이내) |
| prob_38/40 | 1.3-1.6 | 250 | tie (게이트 off) |
=> 4개 명확 이득(+3.6~5.5%), 실회귀 없음. **window-LNS/directions-tail과 달리 이번엔 full-solver서
   실제로 잡힘** — 이유: 코너를 step1로 제대로 평가 + PRIMARY 예산(tail 굶주림 회피).

### 정직한 한계 (coreperi 교훈)
- 훈련 인스턴스 기준. 히든 전이 미검증(coreperi도 로컬 좋았다 히든 회귀). 단 이번은 full-solver
  A/B + 2회 재현 + 게이트 + 회귀체크로 coreperi보다 훨씬 견고하게 검증됨.
- 코너 워커가 worker-1 bigleft-primary 대체 -> best-of+게이트가 보호(n<=160선 bigleft tail도 완주).
- pool-timing 노이즈 ~2% -> 작은 효과는 분해 불가, 큰 이득(+3.6~5.5%)은 노이즈 초과.
submit_v37.zip 생성. v36(무위험) vs v37(중밀도 이득, 작은 히든리스크) 선택은 사용자.

---

## free-span 직접 최적화 (사용자 선택: 중밀도 일반화 배치) — 2026-07-09

### 아이디어
중밀도 배치의 본질 = "빈 공간 통합(시간축으로 최대 연속 free 영역 유지)". 하드코딩 방향
(bigleft/corner) 대신 "놓은 뒤 남는 free-span을 직접 최대화" = 원리적 일반화 시도.
mode="freespan" 추가 (prototype/myalgorithm_freespan_research.py).

### 반복 개선 (1D -> 2D-proxy)
- 1D(바닥밴드 gap only): bigleft는 이기나(+3.5~6.4%) corner엔 짐(+10~14.5%). 2D 못 봄.
- vertical bias / flat-primary 튜닝: 실패 (prob_25 -5%~+0.2%).
- ★ MULTI-BAND(K=4 높이밴드별 free-span의 MIN = 전높이 free column 폭 proxy):
  구성속도 bigleft와 동일(9.1s, scoring 아닌 feasibility가 병목), 크게 개선.

### 결과 (freespan vs cornerBest, 둘 다 vs bigleft, 구성단계)
| inst | ratio | freespan | corner | 승자 |
|---|---|---|---|---|
| prob_22 | 0.53 | -9.6% | +7.9% | corner |
| prob_29 | 0.55 | -1.2% | -2.5% | bigleft |
| prob_24 | 0.60 | **+16.4%** | +10.3% | **freespan** |
| prob_21 | 0.78 | -3.4% | +8.3% | corner |
| prob_23 | 0.86 | **+2.3%** | -0.4% | **freespan** |
| prob_28 | 0.88 | +3.3% | +3.6% | ~tie |
| prob_30 | 0.90 | -10.0% | +9.2% | corner |
| prob_26 | 1.00 | +6.3% | +18.3% | corner |
| prob_25 | 1.29 | +7.9% | +14.5% | corner |

### 결론 — 단일 규칙 일반화는 없다. best-of가 정답.
- freespan은 **원리적 규칙인데도 혼돈적**: prob_24(+16%, corner보다 큼)·23 이기고, 저밀도
  (22/30) -10%로 크게 짐. corner·bigleft·freespan 각자 다른 인스턴스서 이김 = 예측불가.
- 중밀도 배치의 실제 구조 = **밀도-게이팅 best-of{bigleft(저/고밀도), corners+freespan(중밀도)}**.
  단일 "똑똑한 규칙"이 아니라 다양성+best-of+게이팅이 정답 (기하 상호작용이 카오스적이라).
- freespan은 best-of의 **가치있는 신규 멤버**(prob_24서 corner +6%p 추가), 대체는 아님.
- 전부 구성단계. full-solver선 축소(v37 corner 배포이득 +3.6~5.5%). 배포하려면 워커 예산
  경합(coreperi 교훈) 고려 + full-solver A/B 필수.

### 다음 (미정)
freespan을 v37 best-of에 추가 + 밀도게이팅 -> full-solver A/B로 배포이득 확인. 단 모드 추가는
4코어 예산 경합이라 이득 대비 신중히. prob_24류(저-중밀도 0.6, 실지각 있음)가 freespan 최적 타겟.

---

## v38 시도: freespan을 밀도-게이팅 best-of에 통합 -> freespan은 full-solver서 무효(illusion #5)
v37(코너-primary, n<=160)에 freespan을 density-ordered로 추가: ratio<0.75 -> [freespan,cornerTL,BL,TR],
ratio>=0.75 -> 4코너. full-solver A/B(v36 vs v38, tl=50):
| inst | ratio | Δobj | 판정 |
|---|---|---|---|
| prob_21 | 0.779 | +6.28% | 코너밴드 OK (v37급) |
| prob_25 | 1.285 | +5.86% | OK |
| prob_28 | 0.878 | +3.61% | OK |
| prob_24 | 0.602 | 0.00% | ★ v37은 +3.86% -> freespan밴드 회귀 |
=> 코너밴드(>=0.75)는 v37급. freespan밴드(<0.75)가 prob_24서 v37 이득 상실. freespan 구성이득(+16%)이
   full-solver 전이 실패(5번째 함정)+cornerBR드롭 손해. => freespan 폐기.

## ★ 최종 결론 (밀도별 대표 배치)
- 저밀도(<0.6): bigleft (공간 무제약, corner/freespan은 Z2/Z3 손해)
- 중밀도(0.6~1.15): cornerTL(코너 best-of) = **v37**, 검증 배포이득 +3.6~5.5%(6.3%), 무회귀, bigleft속도
- 고밀도(>1.15): bigleft (물리 벽, near-optimal)
=> 중밀도 최종답 = v37. 단일규칙 일반화 없음(freespan도 혼돈적). 밀도게이팅 best-of가 정답이고 v37이 그것.
   (NOTE: 아래 적응형 코너가 v37의 하드코딩 n-게이트를 대체 -> 최종은 적응형.)

---

## 적응형 코너 (하드코딩 n-게이트 제거) — 검증 완료 2026-07-09
사용자 지적("n<=160 하드코딩"). n 대신 step-1 구성비용을 **측정**해서 코너 실행 여부 결정.
odd hybrid 워커: bigleft step2(빠른 baseline+측정) -> step1_est=step2*3 -> 코너 step1은 "한 개가
남은 예산에 들어갈 때만" 실행, 아니면 bigleft 유지. 굶주림 원천 제거(bigleft 항상 완주).
full-solver A/B(v36 vs adaptive): prob_21 +4.68%, prob_24 +3.86%, prob_25 +4.84%, prob_28 +4.47%,
prob_38(n=250) tie(안전). => v37 이득 유지 + 하드코딩 제거 + 고밀도 안전. prototype/myalgorithm_adaptive_corner.py.

## 작년 1등팀(OGC2025) 알고리즘 분석 + Gurobi 판단
업로드 분석: OGC2025는 **그래프 라우팅/네트워크플로우 문제**(노드/포트/OD수요/차량비용, deck graph).
1등팀 = **Gurobi로 MILP 정식화**(binary x_pqi 적재, y_pi 접근성, integer z_pqr 수요분할 + flow보존).
Gurobi 튜닝: barrier(Method=2), crossover off, NoRelHeur(대형), Heuristics=0.15, MIPGapAbs=2.
=> **완전히 다른 문제라 알고리즘 자체는 전이 안 됨.** 그 문제는 MILP-friendly(플로우)라 Gurobi가 근최적.
우리(OGC2026)=2D 불규칙 패킹+스케줄+크레인+레이어interleaving=기하문제라 MILP 부적합.
Gurobi 판단: (1)우리 병목은 solver 강함이 아니라 **기하 relaxation 품질**(레이어interleaving로 area완화
가 loose)-CP-SAT로 이미 벽 확인. Gurobi도 같은 loose모델이면 개선 안 됨. (2)환경에 Gurobi 미설치+
라이선스 필요-OGC2026 채점환경 지원여부 확인이 선결. (3)가능성 있는 각도=Gurobi를 exact 스케줄
backbone/LNS repair oracle(logic-based Benders: MILP master=bay+order+tardiness, 기하=feasibility
subproblem+no-good cut)-단 tighter 기하 relaxation이 관건(연구문제). 전면 MILP는 비현실적.

---

## 패턴기반 ILP 프로토타입 (사용자: Gurobi로 재정식화) — 2026-07-09
OGC2025 1등=Gurobi MILP(라우팅). 우리도 ILP 재정식화 시도. prototype/ilp/pattern_ilp.py (CP-SAT=Gurobi대역).
추가제약(탐색↓): A1 위치=coarse grid 이산화, A2 진입시각 이산화, A3 기하/크레인 사전검증→배치후보에
bake-in(충돌쌍만 y+y'<=1), A4 3자충돌은 공식checker→no-good cut(Benders). 휴리스틱 해로 풀 seed(warm-start).

### 결과 (prob_24 sub-instance)
| n | 휴리스틱(단일구성) | ILP | 풀솔버(ALNS) |
|---|---|---|---|
| 30 | 380990 | 206015 | **4455 (Z1=0!)** |
ILP는 약한 단일구성을 -46% 이기나(iter0 수렴, 빠름), **풀 솔버에 46배 짐.** 풀솔버 n=30 Z1=0(지각 완전제거=최적).

### 근본원인 (illusion #6, 그러나 기전 명확)
1. **이산화가 패킹품질 파괴**: 풀솔버 연속 NFP는 촘촘히 넣어 모두 제때입장(Z1=0). coarse grid는 못 넣어 지각발생.
   "탐색 줄이는 제약"을 너무 세게 걸어 좋은해 배제 = trade-off 실패.
2. **scale-vs-value 불일치**: ILP tractable한 곳(소형/저밀도)=풀솔버 이미 Z1-최적(여지0);
   ILP 도움될 곳(대형/고밀도 지각강제)=계산불가. 풀 수 있는 곳엔 이득 없고 이득 있는 곳은 못 푼다.

### 판정
ILP/Gurobi 재정식화는 우리 풀솔버 못 이김. solver 강함이 아니라 **모델링(연속기하 이산화)** 문제라 Gurobi도 동일.
1등 Gurobi는 그 문제(라우팅)에 연속-기하 이산화 문제가 없어서 통한 것. 우리 기하문제엔 trade-off 불리.
=> 프로토타입 검증으로 Gurobi 전면투자 전에 걸러냄. 우리 휴리스틱 엔진이 이 기하문제엔 이미 매우 강함(저밀도 Z1최적).

## ★ 프로토타입2: 고정패킹 + exact 스케줄 MILP -> Gurobi 방향 개념 검증 성공 (마진 작음)
사용자 반박("Gurobi 대회지원인데 안될 리 없다"). 참신제약 = 위치 이산화 X, full solver 연속패킹을 FIX
-> 지각은 진입시각만(exit=entry+p) -> exact 스케줄 최적화(disjunctive). 충돌=그 위치서 공존불가쌍
(순차진입 검증! 동시진입 아님 <- 이게 처음 실수). lazy-conflict Benders(checker 위반쌍 추가). CP-SAT(=Gurobi대역).
prototype/ilp/schedule_ilp.py.
| inst | ratio | full Z1 | MILP Z1 | |
|---|---|---|---|---|
| prob_38 | 1.57 | 2629 | 2626 | MILP -0.1% |
| prob_40 | 1.33 | 2686 | 2684 | MILP -0.07% |
| prob_26 | 1.00 | 598 | 597 | MILP -0.17% |
| prob_33/25 | 1.14/1.29 | - | tie | 스케줄 이미 최적 |
=> **exact 스케줄이 그리디 이김(검증)**. 단 고정패킹이라 마진 작음(~0.1%): ALNS가 이미 near-opt 스케줄.
   진짜 여지는 PACKING인데 그건 이산화하면 품질손실(프로토타입1 실패). 
결론: (1) 사용자 옳음-Gurobi/exact 통함. (2) CP-SAT로 했으니 **Gurobi 없이도 배포가능**(never-worse 후처리).
(3) 큰 이득엔 packing 공동최적화 필요(기하 난제). 고정패킹 스케줄만으론 ~0.1% 안전이득.

## ★ 조선소 불규칙블록 배치 휴리스틱 조사 -> 양방향 diagonal-fill 검증 (no gain, illusion #7)
Frontiers 2026(불규칙 조립블록 크루즈선) + Kwon&Lee diagonal-fill 문헌 조사.
핵심 문헌 기법:
- **양방향 diagonal-fill(Kwon&Lee)**: 배치후보를 이미 놓인 블록의 BL점뿐 아니라 TR점도 -> 대각 양끝에서 채움.
- **corner-guided sorting**(DDNS2015), **Q-learning hyper-heuristic으로 layout rule 선택**(Frontiers2026).
  => 후자는 "단일 규칙이 전 인스턴스 못 이긴다 -> 규칙 포트폴리오+선택기"가 SOTA framing = 우리 best-of/adaptive가 옳음의 방증.

구현: place_custom에 mode="diagfill"(큰블록이 BL코너 vs TR코너 中 가까운쪽으로 분할 -> 가운데 연속 free-band;
bigcorner의 2D대각 버전), best-of 꼬리에 env-gated 추가(DIAGFILL=1). 격리 풀솔버 A/B(1프로세스=풀CPU):
| inst | ratio | base | diagfill | |
|---|---|---|---|---|
| prob_21/24/28/40 | - | - | - | tie |
| prob_25 | 1.29 | 528220 | 533853 | -1.1% 손해 |
| prob_33 | 1.14 | 78.9M | 83.4M | -5.7% 손해 |
=> **이긴 곳 0.** 병렬 A/B에서 보인 prob_25 -10%는 CPU굶주림 노이즈(격리시 obj 9.39M->0.53M 정상화, 이득 소멸).
원인: 우리 코너패밀리(bigcorner=좌우분할, cornerTL/BL/TR/BR)가 diagfill 효과 이미 커버 -> 중복. 순효과는 ALNS 벽시계 절도.
DIAGFILL 기본 off라 배포 무영향. **문헌기법 정직 검증 완료: no gain.**

## ★ v39 = adaptive-corner + best-of 코드정리 (동작보존 리팩터)
v39 = v36 + adaptive corner best-of(하드코딩 n게이트 제거; step-1비용 실측 게이팅; 중밀도 +3.9~4.8% 실측) 를
제출본으로 확정 + best-of 체인 코드정리.
정리 내용: keep-if-strictly-better 비교가 ~9곳 복붙된 것을 `_best=[cell]`+`_keep()` 하나로,
diagonal/leftbottom/bigleft 3개 동일보일러플레이트 꼬리를 `_tail(mode)` + `for _tm in (...)` 루프로 축약.
**_attempt 호출 순서·시간게이트·비교 전부 불변 -> 동작보존.**
검증(격리 풀솔버 base vs v39): prob_24/28/38 **바이트동일**(1219453/4232590/2655622427), prob_33만 발산했으나
base-vs-base(100.36M)와 v39도 100.36M 재현 -> prob_33 고유 ALNS타이밍 분산(~15%)이지 리팩터버그 아님 확정.
산출물: prototype/myalgorithm_v39_clean.py, submit_v39.zip(support 4파일 v36과 바이트동일, myalgorithm.py만 변경).

## ★★ v40: FREE-REGION 증분 구성 — 대형 고밀도 구성 병목 해결 (prob_40 -46%)
문제 진단: 대형(n=250) 구성이 60초 예산 초과(step=1 bigleft 95~104s). 원인은 기하연산 속도가
아니라 **시간축 재스캔** — 블록이 안 들어가면 이벤트(블록 이탈)마다 전체격자 재스캔. 실측 재스캔
배수: prob_38=13x, prob_40=14.6x(최대 71회). 그래서 step=1 품질을 못 쓰고 step=2 저품질 폴백.
+ 더 많은 시간 = 큰 이득 확인(prob_40 60s→180s = -52%): compute가 binding.

해법(FREE-REGION): 밀도 단조성 — 블록 X 이탈 시 새 자리는 오직 X가 비운 footprint 구역에서만
생김(크레인 진입충돌 = footprint 겹침). 그러니 재스캔 때 **비워진 구역 주변 윈도우만** 스캔.
place_custom에 windows 파라미터 추가, (ix,iy) 오름차순 유지 → 스코어링 타이브레이크 동일 →
**BYTE-IDENTICAL 출력**(모든 모드 검증: bigleft/corner*/diagonal/leftbottom). ogc_fast 사용,
cranecheck .so 의존성 0. 구성 byte-identical + ALNS 시간↑ = **수학적 never-worse**(ALNS는 best 유지).

측정(격리, 60s, 진짜 C++ 엔진 py3.12):
| inst | n | v39 | v40 | |
|---|---|---|---|---|
| prob_40 | 250 | 3,688,471 | 1,989,054 | **-46.1%** |
| prob_39 | 250 | 7,962,220 | 7,843,733 | -1.5% |
| prob_33 | 200 | 7,684,850 | 7,605,106 | -1.0% |
| prob_38 | 250 | 37,825,961 | = | tie |
| prob_31 | 200 | 6,915,839 | = | tie |

게이트: n>=200에서만 활성(대형=temporal rescan 지배). n<200은 v39와 **byte+timing 동일**(회귀 0).
중요 디버깅: free-region init(dict/list 할당)이 무조건 실행되면 멀티프로세싱 워커 타이밍을 교란해
타이밍-민감 인스턴스(prob_24) 결정성을 깸(993419<->1021744). init을 `if _fr_on` 가드 -> 복구.
prob_27(n=150,고밀도)의 -3.2%는 n게이트에 걸려 잃음(안전 트레이드). 산출물: submit_v40.zip,
prototype/myalgorithm_v40_freeregion.py. 지원파일 4개 v36과 바이트 동일, myalgorithm.py만 변경.

프로파일링(에이전트): dead code ~590줄(orphan 함수 _entry_ok/_exit_ok/_footprint_verts/
_redistribute_pref/_crane_open/_corridor_open/_atc_order + 비활성 CP-SAT/GLS/IL 서브시스템),
hot-path B1(_bay_unit_weights 반복재계산) B3(_objective 매 반복 전체재계산). B1은 타이밍 교란
위험으로 보류. B3(증분 objective)는 repair가 지배적이라 이득 불확실+고위험으로 보류.
