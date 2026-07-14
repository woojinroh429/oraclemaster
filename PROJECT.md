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

## v40 후속: 죽은 코드 제거 (동작 중립)
프로파일링이 확인한 orphan 함수(참조=def뿐) 제거: _entry_ok/_exit_ok(677-684),
_redistribute_pref/_crane_open/_corridor_open/_atc_order(연속 1793-2116). 총 332줄 삭제
(myalgorithm.py 4290->3959줄). 검증: prob_24=993419, prob_40=1989054 불변 -> **런타임 동작 중립**
(죽은 코드는 실행 안 되므로). _footprint_verts는 인접 live _NFP_MODE + cache clear 얽힘으로 보존.
submit_v40.zip 갱신(정리본, 동작 동일).

## ★★ v41: 대형 고밀도 전용 구성-완성 워커 (prob_40 추가 -12.6%, prob_38 -8.8%)
진단: `_alns`/polish는 P6 지각(Z1)을 못 줄임(구조적, 코드 주석도 인정). 대형 점수는 구성 완성도가
전부인데, 완성된 bigleft step=1(1.77M) > 풀솔버(1.99M)였음 -- 솔버가 멀티워커 예산분할로 최고 구성을
못 완성. 해법: `_worker_entry`에 DEDICATED 워커(bl_full 플래그, 17번째 arg) 추가 -- n>=200 & hi_ratio
& not P5에서 마지막 워커(numba guard)를 재활용해 bigleft step=1을 거의 전예산(timelimit-2)으로 완성,
shared best-of에 기여. never-worse: 완성하면 이김, 못하면 best-of가 무시(다른 워커+_safe_sequential이
feasible 보장). free-region이 구성을 55초로 줄여 예산 안에 완성 가능해진 게 전제.
측정(격리 60s): prob_40 1,989,054->1,738,953(-12.6%), prob_38 37,825,961->34,512,341(-8.8%, 천장 정확),
prob_31 -3.3%, prob_33 -0.4%; prob_39/22 tie; 소형(n<200) dedicated off -> 무변화(prob_24=993419 결정론적).
v39 대비 누적: prob_40 -52.9%, prob_38 -8.8%. 산출물: submit_v41.zip, myalgorithm_v41_dedicated_worker.py.

## ★★★ v42: 선호-인식(prefaware) 구성 -- 저/중밀도 Z3 레버 (prob_24 -42%, prob_21 -10%, prob_28 -8%)
수학적 발견: 저/중밀도 objective의 질량이 지각(Z1)이 아니라 **선호위반(Z3)에 있음** (측정: prob_28 Z3=55%,
prob_31 Z3=50%, prob_24 Z3=96%!).  모든 packing 모드(bigleft/corner/...)가 베이를 packing으로만 고르고
블록 선호베이를 무시(`sc=(...,j)`에서 j=인덱스 tiebreak) -> Z3 방치.  polish(_pref_reassign/_swap_polish)도
겨우 -9% (prob_31은 오히려 Z3 증가, ALNS가 Z1위해 희생).  즉 Z3 질량이 통째로 방치.
해법: mode="prefaware" -- 각 블록을 선호베이 우선 배치(sc=(pref_pen, h, wx, wy); 작은블록 (pref_pen,-fs,..)).
best-of 꼬리에 추가(n<200 게이트) -> Z3지배는 prefaware 승, Z1지배는 bigleft 승 = never-worse.
측정(격리 60s, PREFAWARE 0 vs 1): prob_24 993419->576132(-42%, Z3 3178->1520), prob_21 -10.3%,
prob_28 -7.7%; prob_22/25/29/30 tie; prob_31(n=200) 게이트로 제외(예산절도 +0.4% 방지); 대형 무변화.
n<200 게이트: 대형은 Z1지배+dedicated worker가 예산 씀.  산출물: submit_v42.zip, myalgorithm_v42_prefaware.py.
P3/P4(중밀도 히든)가 Z3지배면 큰 이득 기대.

## ★ v43: prefaware 게이트를 블록수 -> 구조적(Z3-share)로 (게이트 강건화)
사용자 지적: 게이트가 블록수(n) 기준이라 허술/비일반적.  옳음 -- n은 "Z3 지배인가"의 크루드 프록시.
수정: prefaware를 n<200 대신 **incumbent 구성의 Z3 비중(w3*Z3/total)>=0.40** 일 때만 실행(구조적, 밀도/크기
무관).  단일 step=1 시도로 예산절도 최소화.  검증: prob_28 -10.7%(n게이트 -7.7%보다↑), prob_24 -42%,
prob_21 -10.3%; prob_30/38/40(Z1지배) Z3-share<0.40 -> skip(무회귀).  prob_31 "+0.4%"는 PREFAWARE=0/1
둘 다 {6.69M,6.72M} 내는 고유 노이즈로 판명(회귀 아님).  never-worse + 일반화.  게이트가 밀도가 아니라
인스턴스 자신의 objective 구성으로 자동결정 -> best-of 자기선택.  산출물: submit_v43.zip.

---

## v44: empty-layer canonicalization (utils.py 일치) — 2026-07-11

### 배경
대회 공지: hidden P3에 **empty layers**가 있었고, 조직위가 "utils.py 데이터 처리를 정확히 따르라"며
인스턴스를 clean-up("빈 레이어 제거, 특성 불변, 올바른 솔버는 동일 해").

### 발견한 버그 (utils.py 불일치)
- utils.py `_resolve_layers`: `[list(l) for l in raw if l]` → **빈 레이어 필터**.
  Block 기준점 = **필터된 첫 레이어의 첫 정점** → (x,y).
- 우리 엔진/템플릿: `shape[oi]["layers"]`를 **raw로 읽음**(_load_ogc_state L116 등) → 빈 레이어
  미필터 → 크레인 레이어 인덱스(j>=k) 및 (x,y) 기준이 utils.py와 어긋남 → 빈-레이어 인스턴스
  (P3류)에서 엔진이 grader와 다른 기하로 판정 → 과보수 패킹.

### 재현 (prob_29에 빈 레이어 삽입)
- 수정 전: CLEAN=542034, EMPTY_{START,END}=547173 (결정론적으로 다름 → 실제 기하 불일치 확정)
- 수정 후: CLEAN=EMPTY_{START,END,MID}=**542034** (완전 일치 → utils.py와 정합)

### 수정
`algorithm()` 시작에서 모든 block/orientation의 layers에서 빈 레이어 필터
(`if any(not _l ...)` 가드 → clean 인스턴스는 미변경 = byte-identical/무손실).
train 20개 전부 빈 레이어 없음 → P1~P6 중 clean 인스턴스 점수 불변, 빈-레이어 인스턴스만 개선.

### 한계 (정직)
단순 2레이어 블록에선 빈-레이어 영향 ~1%. P3의 복잡한 다층 구조에선 증폭 가능하나 hidden 실물이
없어 정확한 크기는 미측정. 재제출로 검증 필요(제출이 clean-up 전이었으면 큰 개선 기대).

---

## v45: 저밀도(P3류) 강한 재배정 -- SA + 재타이밍 -- 2026-07-11

### 진짜 P3 발견 (미사용 데이터셋!)
- `data/training_instances/train`(prob_1~20)이 **전부 저중밀도(ratio 0.28~0.48)** = P3 프로필.
  이 세션 내내 mid-high 세트(prob_21~40)만 써서 P3 재현을 못했던 것. (사용자가 "trainset1" 지적)
- 리더보드: P1/P2 전원 동일(수렴), **P3 최상위 ~82k, 우리(kgu_mis_21) 165,930 = 2배.**
- 저밀도 목적 = Z1=0, **Z2+Z3 지배**(선호/부하). prob_4 Z3 82%, prob_6 Z3 heavy.

### 버그 = 약한 재배정
- `_pref_reassign`: 진입시각 고정 + greedy(엄격개선만) + 6패스 → 저밀도·선호쏠림·다베이에서
  지역최적에 크게 갇힘. 측정: **prob_6 우리 98k vs 달성가능 66k(-32%)**, prob_4 -14%.
- 누락 자유도 2개: (1) **재타이밍**(저밀도 슬랙 크니 마감 전까지 미뤄 선호베이 빈 시점에 진입,
  Z1=0 유지), (2) **uphill(SA)** 탈출.

### 수정
1. `_sa_reassign`: 재타이밍 + SA 재배정 연산자 (엔진 feasibility, best 반환, check_feasibility 게이트).
2. 폴리시 체인에 추가 + `_low_density`(construction Z1-share<0.5) 게이트.
3. 저밀도일 때 `POLISH_RESERVE 0.12->0.6` = ALNS(패킹/Z1, 저밀도선 무용) 예산을 재배정으로 이전.
   플래그는 base_chk(기존 계산)로 산출 → 고밀도엔 추가 연산 0.

### 검증 (v44 vs v45, 동일 예산)
- 고밀도 prob_38=34,512,341 / prob_40=1,989,054 : **byte-identical** (게이트 스킵)
- 중밀도 prob_28=2,677,407 / prob_24=948,769 : 무회귀
- **저밀도 prob_6 98,257->63,906 (-35%)**, prob_4 -8.6%, prob_9 -5%, prob_20 -1%, prob_1 불변
- 전부 never-worse (best-of + check_feasibility 게이트). 25s 예산 기준이라 60s선 더 클 것.

---

## v46: 정확 CP-SAT 배정 -- 작은 저밀도(P3류) -- 2026-07-11

### 동기
저밀도(Z1=0)는 목적이 Z2+Z3, 핵심 결정은 "어느 베이" = 작은 배정문제. SA/greedy가 지역최적에
갇힘(예: prob_4에서 Z3=0 배정으로 가는 경로가 Z2 증가 상태를 거쳐 local search가 거부 -> Z3=236에 갇힘).
CP-SAT은 전역 배정 최적으로 직행.

### 모델 (`_exact_reassign`)
min w2*Z2 + w3*Z3, s.t. 각 블록 1베이 + (베이,release시각)별 면적합<=용량(Z1=0 필요조건).
면적제약은 완화(면적!=폴리곤+크레인) -> 배정을 실제 엔진 구성으로 realise, feasible & better일 때만 채택.
기하 실현 불가(Z1 폭발/infeasible)면 best-of가 무시 = never-worse. CP-SAT<1s (n=300,m=5도 0.5s), 1스레드.

### 결과 (full solver, v45.1 대비)
- **prob_4: 58582 -> 15946 (-73%!)** Z3=0 달성 (전원 선호베이, 기하 실현됨)
- **prob_2: 5890 -> 3690 (-37%!)** Z2 대폭 감소
- prob_6/3/5/20: 정확법 실현 실패 -> best-of가 SA 결과 유지 (무회귀, prob_6=64728)
- prob_38(고밀도): 34512341 byte-identical (저밀도 게이트라 스킵)

### 파이프라인 (저밀도, Z1-share<0.5)
construction -> (ALNS 축소, POLISH_RESERVE 0.6) -> _exact_reassign(전역배정, ~15s) -> _sa_reassign(정제).
전부 best-of + check_feasibility 게이트 -> never-worse. 고밀도는 전부 스킵 = byte-identical.

---

## v47: Logic-based Benders -- 어려운 저밀도 exact 실현 -- 2026-07-11

### 배경
v46 정확배정은 쉬운 저밀도(prob_2/4)만 실현(-37~73%), 어려운 저밀도(prob_3/5/6=P3류)는 면적완화가
너무 느슨해 기하 실현 실패(Z1 폭발)->best-of가 버림. 리더보드: v46 제출 P3 165930->147335(-11%),
최상위 ~82k라 아직 1.8배.

### Benders 루프 (`_exact_reassign` 확장)
면적제약은 진짜 기하+크레인 packability의 느슨한 완화. 각 라운드:
1. MIP(현 용량) 풀어 배정 -> 2. 엔진 실현 -> 3. Z1=0이면 성공/종료
4. Z1>0이면 peak 면적이용률 최대인 베이의 유효용량 *0.88 -> 재solve.
=> MIP이 각 베이의 진짜 packing 한계를 학습. 최대 5회, 실현되는 최선 반환.
안되면 best-of가 SA 유지 = never-worse.

### 결과 (full solver 50s)
- **prob_6: v46 64k -> 57783 (-10% 추가)** (Benders it4에서 Z1=0 실현)
- prob_4: 15946 유지 (it0 즉시 실현)
- prob_9: 61210 무회귀
- prob_38(고밀도): 동일부하·예산서 v46=fr2=37825961 byte-identical (저밀도 게이트 스킵)

### 예산
저밀도 폴리시 예산(POLISH_RESERVE 0.6) 중 exact에 최대 24s(호출부), 나머지 SA. 60s 채점서 수렴.
30s 등 짧으면 Benders 미수렴이지만 never-worse(SA수준).

## ★★★ 저밀도 목적함수 완전분해 — 밤샘 연구 (2026-07-11 야간)

동기: v48 제출 P3 149620 (v46 147335 대비 +1.5%, 측정변동 4% 내 = 노이즈). 저밀도(P3류)
레버를 바닥까지 규명. trainset1(prob_1~20, ratio 0.28~0.48) 전수 60s 풀솔버 + CP-SAT LB 측정.

### Q1: 저밀도 지각? → **20/20 전부 Z1=0.** 지각 완전소멸. Z1은 저밀도 레버 아님.
목적함수 = 순수 w2·Z2 + w3·Z3. (v48 P3 회귀도 Z1 아닌 Z3 실현노이즈 확정.)

### Q2: Z3는 왜 증가하나 → 선호집중 구조적하한 + 크레인프리미엄
- Z3 = Σ(max_pref − pref[배정베이]). 무한용량이면 0. 전부 "용량/균형이 블록을 선호베이 밖으로
  밀어낸 비용".
- 전블록 최선호배정시 베이 피크부하%: prob_1/2/3/4/8은 모두 ≤100%(=Z3 거의 크레인프리미엄),
  prob_5/6/7/9~20은 일부 >100%(prob_10 bay0=220%, prob_19 243%, prob_20 258%) = 선호가
  과부하 베이에 집중 = Z3 **구조적 하한**(완벽패킹으로도 밀림).

### Z3 갭 = 우리Z3 − CP-SAT area최적Z3lb (핵심 지도)
```
갭0(최적): prob_1(2/2) prob_2(15/15) prob_4(0/0) prob_8(8/8)  ← 이미 최적, 레버없음
갭>0(16개, Z3가 obj의 60~96% 지배):
 prob_20 gap762×w3125=95250  prob_13 573×133=76209  prob_12 459×133=61047
 prob_14 410×133=54530  prob_18 295=39235  prob_17 291=38703  prob_9 237×150=35550
 prob_11 234×133=31122(wZ3 96%!)  prob_15 230  prob_16 167  prob_10 124  prob_5 183
 prob_6 182  prob_7 93  prob_3 65  prob_19 67
 16개 합 ~750,000 회복여지. n 클수록 갭 큼(스택이 스케일서 약함).
```

### 목적함수 정의 검증 (utils.py 1403~1430)
- obj1=Σmax(0,exit−due). obj2=floor(max_pairs|u_j·load_j−u_k·load_k|), u_j=avg_area/area_j.
  obj3=Σ(max_pref−pref[bay]). CP-SAT는 W2·Mv+W3·SC·Z3로 **정확히 W2·obj2+W3·obj3 최소화**
  (SC=1000). 모델 옳음. 유일 완화 = area용량 vs 크레인용량.

### 네거티브 결과 (측정으로 배제한 레버들)
1. **크레인-aware 배치 배제.** 크루드 `_L*_dw`: 로버스트승리 prob_1 하나(그마저 flatbl도 동률).
   정확한 하강-마스크(top-layer 노출최소화): prob_3/11/18에서 prefaware보다 훨씬 나쁨, deep-layer
   실현조차 실패. 레이어분석: 90% ≤2레이어, 63% 솔리드(캔틸레버불가) → 하강차원 여유 거의 없음.
   in-loop통합은 CP-SAT 비결정성으로 궤적교란(prob_6 +270%). → 완전 사망.
2. **α-tightened 용량바운드 배제.** capj=α·cap(α=0.8~1.0)+단일샷 best-of실현: 어떤 α도 Z1=0
   못만들고 전부 풀솔버(prob_5 68786)보다 나쁨(94667+). SA가 이미 더 잘함.
3. **mode-diversity 실현:** 격리서 flatbl/leftbottom이 prefaware 이기는 듯 보였으나(prob_1 −95%),
   풀솔버가 이미 SA로 그 해를 잡음(prob_1 obj1499=최적). 격리실험 과대평가. 풀솔버 실효 미검증.

### 핵심 미해결 (진행중): 저밀도 obj가 시간/탐색 제한인가 크레인-최적인가?
- area최적 배정은 큰갭 인스턴스서 크레인-불가능(prob_11/18 전모드 Z1=27~66 spill). 갭 일부는
  불가피 크레인프리미엄.
- BUT 경쟁자 P3 ~82k vs 우리 149620 = 2× → 더 나은 저밀도해 존재 방증.
- 60s vs 300s 풀솔버 실험중: obj 떨어지면 탐색제한(레버), 평평하면 크레인최적근접.

### 야간 후속: 탐색 레버 검증 (INCSA 반증 + 고변동 발견)
- **증분 SA(INCSA) 반증.** `_sa_reassign`이 iteration당 엔진 전체재구축(O(n))이라 큰 인스턴스서
  SA 적게 도는 걸 발견 → 엔진 remove/add로 O(1) 증분화(게이트 INCSA, remove 검증). A/B(6갭인스턴스):
  prob_11 한 번 −19.5%(49294→39690) 나왔으나 **3반복시 재현 실패**(INCSA=1: 49245/49245/49644 vs
  INCSA=0: 48958/48839/48839). = 운좋은 아웃라이어. 다른 인스턴스 전부 중립~약간나쁨. **"SA iteration
  수가 병목"은 틀림** — 더 돌려도 같은 local optimum 수렴.
- **★ 폴리시 고변동 발견.** prob_18 동일코드 2런: 62182 vs 67603 = **8.7% 변동.** prob_12 diag 103642
  vs 재측정 109865 = 6%. **저밀도 폴리시가 수렴 안 하고 런마다 다른 local optimum.** 이것이 v48 P3
  "회귀"(147335→149620, +1.5%)의 진짜 정체 = 코드회귀 아닌 변동. **변동축소(항상 좋은쪽 뽑기) 자체가
  레버 후보** — best-of-N 재시작. SA가 빨리 수렴하므로(INCSA 방증) 짧은 재시작 다수 + best-of가 budget
  내 가능. 검증 예정.

### ★★★ 레버 발견: SWAP 이동 (저밀도 SA reassign) — 2026-07-11 야간
INCSA(iteration↑) 실패로 "병목은 이웃구조"를 반증적 확인 → SA에 SWAP 이동 추가(b를 tj의 b2와 교환).
증분엔진(remove/add) 위에 구현(게이트 SWAP). **단일이동은 과선호-포화 베이가 차면 막히지만 교환은 뚫음**
= Z3 갭(선호베이서 밀린 블록)의 직접 공략.

전체 trainset1 SWAP vs BASE (풀솔버 60s, 단일런):
```
큰 승리: prob_11 −41.1%  prob_18 −16.3%  prob_9 −13.2%  prob_13 −10.0%  prob_14 −6.0%
         prob_15 −5.5%  prob_12 −2.4%  prob_5 −2.1%  prob_6 −1.9%  prob_16 −1.9%
불변: prob_1/2/4/7/8/17 (이미최적/컨트롤)   미세: prob_3 −0.1% prob_20 −0.3% prob_19 +0.3%
회귀: prob_10 +11.0% (검증중)
```
13개 개선(다수 대폭), 회귀 1개. 압도적 순-양성. prob_11 Z3 354→215(갭 234→95, 60% 닫음).
_sa_reassign은 저밀도 polish에서만 호출 → 고밀도(P4/P5/P6) 무영향. 통합시 worker-diversity 또는
_keep_reassign(min)로 never-worse 보장(prob_10 가드) 필요. 단일런 측정은 pessimistic(프로덕션은
4워커 best-of가 swap 변동 tail을 잡음). = free-region이 원리적 가속이면 SWAP은 원리적 이웃확장.

### ★★★ v49: SWAP 이동 통합 (저밀도 Z3 레버) — 2026-07-12
SA reassign에 교환(swap) 이동 추가 = 저밀도 Z3 갭 직접 공략. 증분엔진(remove/add, O(1)/move) 위에
구현, all-swap(전 워커 full 예산, SWAPPOL 기본 ON). 저밀도 polish 전용이라 고밀도 무영향.

**변동 관통 median A/B (POL0=v48 vs POL1=swap, 3반복 median):**
```
prob_11 −16.7%  prob_9 −13.2%  prob_14 −12.8%  prob_10 −7.6%  prob_15 −7.5%  prob_6 −1.6%
prob_19 +0.4%(중립)   회귀 0
```
초기 단일런 "회귀"(prob_6 +5.8% 예산분할 / prob_10 +11% 변동)는 아티팩트로 확정. all-swap이 깨끗한 승자.

**검증:**
- 고밀도 P4/P5/P6(prob_27/38/40): SWAPPOL 0 vs 1 **바이트동일**(24177428/34512341/1738953) — swap은
  저밀도 전용(_sa_reassign은 저밀도 polish에서만 호출).
- .so 3개 + utils.py = submit_v48.zip과 완전 동일(swap을 실제 제출 엔진으로 검증).
- 프로덕션 default(env 없음) = SWAPPOL"1" = swap ON.

**메커니즘:** Z3 갭 = 과선호 베이서 밀린 블록. 단일이동은 선호베이가 차면 막힘. 교환(b↔b2)은 뚫음
= 낮은-Z3 배정을 Z1=0으로 실현. free-region이 원리적 가속이면 swap은 원리적 이웃확장.

산출물: submit_v49.zip, prototype/myalgorithm_v49_swap.py. (실험 dead code craneaware/cranemask/
CRANEAWARE는 파일에 남아있으나 기본값이 원본동작이라 inert; cleanup은 follow-up.)

**최종 확정 (전체 20개 단일런, POL0=v48 vs POL1=v49):** 회귀 0, 15개 개선(−1.9~−16.7%),
나머지 불변. 대형 Z3-갭 다 개선: prob_18 −14.5%, prob_5 −10.5%, prob_13 −7.2%, prob_12 −6.4%.
trainset1 합계 net ~−6%. median 검증과 일치. v49 확정.

### 야간 후속: swap 강화 시도 + 저밀도 속도 측정 (2026-07-12)
- **속도(throughput):** 저밀도 SA ~500 iters/s (n=200 블록당 25이동, n=300 블록당 8이동). 병목은
  이동마다 `_fp_timed`(대상베이 배치 스캔), 엔진 아님(INCSA로 이미 O(1)). = SA는 **이동 횟수가 아니라
  이동당 비용에 제한.** 그래서 raw iteration↑(INCSA)이 안 통했던 것. 레버는 "더 많이"가 아니라 "더 똑똑".
- **directed swap 반증:** 랜덤 파트너 대신 "ocur 최선호 b2" 선택 → accept율 5-10× 폭증(prob_9 4→46).
  하지만 obj는 나빠짐 — 순수 max(80%) prob_18 악화, **top-3 균형도 median서 random보다 나쁨**
  (prob_18 +11.9%, prob_15 +1.4%). 그리디 편향이 탐색을 죽여 나쁜 basin에 갇힘. **random swap이 최선.**
  v49 = random swap 확정(directed 폐기).

### v49 정리 + 저밀도 SA 효율화 (제출본) — 2026-07-12
사용자 요청: 저밀도 코드 예산 효율화 + 불필요 기능 제거.
- **죽은 실험코드 전부 제거**(전부 gated-off, 프로덕션 미실행이었음): FBP(C++ 스캔, 실패),
  CHAIN(3-cycle, prob_11 +20% 회귀), SWAPDIR(directed swap, 실패), SADBG(카운터),
  craneaware/cranemask 스코어링 + present_top/_topbb, _exact_reassign의 CRANEAWARE mode-diversity
  분기. myalgorithm.py 228KB→220KB.
- **swap을 param 하드코딩**(swap=True, 프로덕션 항상 ON). SWAP/SWAPPOL/INCSA env 제거.
- **★ 저밀도 SA 핵심 최적화 (프로파일 발견):** viol 계산이 매 iteration마다 n개 블록의
  max(bay_preferences)를 재계산 = builtins.max 250만 호출 = SA CPU의 ~41%. 이 값은 SA 중 상수라
  루프 밖에서 1회 precompute(_mxpref) → max 호출 67%↓(250만→82만), SA ~1.5× 가속. 의미 동일.
- **검증:** 고밀도 prob_27/38/40 바이트동일(24177428/34512341/1738953, SA는 저밀도 전용).
  저밀도 합계 clean −0.1% / opt +0.2% (v49 swap 대비, 노이즈 내) = 행동 동일, swap 이득 보존.
- **C++ 사용 진단:** 구성(find_best_placement)·CP-SAT(ortools)·엔진 remove/add는 C++로 잘 씀.
  SA 배치스캔(_fp_timed)은 Python 루프가 셀마다 C++ placement_feasible 호출 → Python 오버헤드
  지배(~500-800/s). FBP(C++ 전수스캔)는 8× 빠르나 위치 휴리스틱이 바닥-왼쪽과 달라 하류 swap
  해쳐 폐기. 진짜 낭비는 위 max-재계산(Python)이었고 잡음. 남은 _objective 증분화는 위험 대비
  이득 작아(throughput↑는 obj 거의 불변, INCSA 전례) 보류.
산출물: submit_v49.zip 재빌드(.so/utils=v48 동일), prototype/myalgorithm_v49_swap.py.

### ★ v49 P3 회귀 근본원인 규명 + P3 천장 분석 (2026-07-12)
사용자: "v49 결과 P3=176030 망했다, 원인이 뭘까, 이것만 줄이면 1등". v48 P3=149620.

**1) 회귀 직접원인 = swap 오버헤드 → SA iteration 기아 (컴퓨트-제한 P3).**
- v49는 저밀도 폴리시 SA를 `swap=True` 하드코딩. swap은 iteration마다 엔진 remove/add(2블록)+
  재스캔 2회+full `_objective`(O(n))를 추가 → iteration당 비용 급증.
- **P3(=prob_20)는 컴퓨트-제한:** 동일코드 예산별 obj = 177111(60s)/151463(120s)/145909(240s)/
  132843(480s). 즉 더 많은 유효 iteration = 더 낮은 obj.
- 결합: 채점기에서 swap 오버헤드가 SA 유효 iteration을 갉아 P3를 컴퓨트-기아 구간(176k)으로 밀어냄.
  통제실험: 동일부하에서 v48 = swap제거 = 176486 **동일** → 코드회귀 아니라 부하-민감도.
- **복구 = swap 제거(swap=False) = v48 거동 = 149620.** (submit_v48.zip 재제출이 무위험 복구.)

**2) P3 근본 갭의 정체 = Z3gap 762 (구조적, 크레인 혼잡벽).**
- prob_20 분해: Z3=997, 면적최적 하한 Z3lb=235, **Z3gap=762 (20개 중 최대)**, wZ3가 obj의 82%.
- `_exact_reassign` per-round 계측(EXDBG): 면적최적 배정(asgZ3=235)을 실현하면 **정확히 1블록(b=32)이
  미배치(299/300)**. 그 1블록 때문에 `len(recs)!=n` → Benders가 과포화로 오판, capf 조임 →
  asgZ3 235→512로 상승, 5라운드 후 best=None(prob_20에 기여 0). SA의 ~980만 생존.
- **1블록을 강제 안착시키면 Z1 폭발:** 저-Z3 배정에서 그 블록은 온-타임 자리가 없어 지각(Z1=35~98,
  ×w1 지배). 인기 베이가 크레인 하강 클리어런스로 ~80%에서 막혀 초과 1블록이 밀려남 = **구조적**.

**3) 시도한 레버 전부 = 신뢰가능한 개선 없음 (측정).**
- **빠른 SA 엔진**(non-swap 경로 영구 증분엔진, FASTENG): 180s A/B rate ~275→~320/s(엔진 재건축이
  병목 아님; `_objective`+`_fp_timed` 스캔이 지배). obj 144955→146824 **1.3% 악화**(궤적 드리프트).
  → INCSA 전례 재확인: throughput↑ ≠ obj↓. **기각.** (기본값 FASTENG=0.)
- **salvage/seed-repair**: 미배치 1블록을 아무 베이나 안착 → Z1 지각. 그 seed를 SA로 수리 → SA는
  Z3/Z2 위반만 타깃, 지각 1블록은 좌표 조정 없이 못 고침(협조이동 필요). **기각.**
- **swap**(=v49): 오버헤드로 회귀. **기각.**
- **예산 재분배**(CHAINF, 저밀도 early-polish 체인 캡→SA에 시간 이전): 120s A/B CF=1.0 mean 145797,
  CF=0.5 158572(+9% 악화), CF=0.3 146559(동급, 분산↑). early-polish가 좋은 base(151k vs 177k)를
  만들어 캡하면 base 악화→SA가 신뢰가능 복구 못함. **기각.** (기본값 CHAINF=1.0.)

**결론:** P3는 현 엔진의 **구조적 천장(~145-150k)**. 단일-이동 SA는 Z3≈980에서 plateau(180s에서
2/4 워커 무개선). 480s의 132k는 파이프라인 전체 컴퓨트↑(재시작·exact 라운드)에서 오지 단일 SA
가속에서 오지 않음 → 채점기 예산에선 도달 불가. **진짜 상금(Z3 235 실현 → obj ~56k)은 인기 베이를
bottom-left보다 강한 크레인-인지 타이트 패커로 채워 밀려나는 1블록을 온-타임 안착시키는 것 = 신규
패커 R&D(고위험).** 마감 전 안전수 = swap 제거 복구(=v48, 149620).

### ★★ v50: SPILL 실현기 — 저밀도 −15% 돌파 + 대규모 코드 정리 (2026-07-12)
위 "1블록이 크레인 벽" 진단이 **틀렸음**을 정밀 계측으로 발견 → 진짜 원인은 **면적/파편화**였고,
이를 뚫는 SPILL 실현기로 저밀도 대폭 개선. (사용자: 크레인-인지 패커 도전 → 진단이 방향을 틀어줌.)

**진단 반전 (prob_20 미배치 b=32 정밀 분해):**
- b=32는 크레인 아니라 **2D 면적**으로 막힘(scan: area_ok=0). 초선호 bay2(pref=95)가 그 시각 25블록
  으로 참. 하지만 **b=32는 bay0/bay3에 온-타임 안착 가능**(addZ3=94) → 구조적 지각 아님!
- 즉 면적최적 배정(Z3=235)은 **실현 가능**하되, 과포화 베이의 초과 블록을 **차선호 베이로 흘려보내야**
  함. 기존 `_smallright_construct(prefaware,ext_bay)`는 강제 배정→못 넣으면 **드롭**(299/300)→Benders
  과포화 오판→Z3 폭등. 이게 P3 갭의 진짜 정체(크레인 아님).

**SPILL 실현기(`_spill_realize`, `_exact_reassign` 라운드0 내부, SPILL=1 기본):**
- 면적최적 ext를 받아 각 블록을 (1)배정 베이 온-타임, 안되면 (2)차선호 베이 온-타임 **spill**(Z3 최소증가),
  최후 (3)late. **6개 dispatch order × grid step(2,1) best-of** = 12실현, check_feasibility 통과 최소값.
  order 다양성이 핵심(그리디는 순서 민감): big/urgent/strong-pref/small/long-stay/space-time first.
- **never-worse**(best-of `_keep_reassign`): SA가 이기는 인스턴스는 spill 폐기. `_exact_reassign` 내부라
  저밀도 전용 → 고밀도 바이트동일.
- **검증(@90s, SP=0 no-spill 대비):** prob_20 133982→**105274(−21%)**, 11 −41%, 12 −14%, 13 −12%,
  18 −13%, 9 −8%, 5 중립. **저밀도 합 −15.4%, 회귀 0.** 고밀도 27/38/40 바이트동일.
- **P3(=prob_20): 149620(v48/채점기) → ~105k, −30%.**

**시도했으나 기각(정직 기록):**
- **C++ spill(`find_best_placement`)**: 5× 빠르나 품질 **+28~98% 악화**. 이유: 얘는 메인구축(밀도/Z1)용
  휴리스틱이라 블록을 **흩뿌려** 빈공간 파편화 → 다음 블록 못 들어감 → spill↑ → Z3↑. bottom-left
  first-fit은 블록을 구석에 **뭉쳐** 연속 빈공간 보존 → spill↓. (구축 FBP 기각과 동일 교훈.) Python
  spill이 1.3s로 이미 충분히 빨라 속도는 병목 아님 → best-of order 확대(2→6)가 진짜 레버(−6~16%).

**대규모 코드 정리(전부 재검증: 고밀도 바이트동일 + 저밀도 spill 유지):**
- 기각 실험 제거: FASTENG(영구엔진, throughput↑≠obj↓ 재확인 −1.3%), CHAINF(예산재분배, base악화),
  SADBG/POLDBG(디버그), SKIP_*/SPILLCPP/SPILLORD(ablation 토글).
- 죽은코드 제거: WASTE/wasteflat 모드(실패실험), 도달불가 construct 모드 5개(interlock/spread/
  bigright/bigtop/bigcorner).
- **후처리 ablation:** shift/temporal/balance/swappol/pref 체인 → 고밀도 전부 바이트동일(무기여),
  저밀도 prob_20 ±0.6%(무기여) but prob_13 -ALLCHAIN +7.6%(단, 저밀도 분산 ±9%로 교란) → **제거
  안전 확증 불가라 보존**(변경으로 미검증 인스턴스 회귀 위험 회피).
산출물: submit_v50.zip(.so/utils=v48 동일), prototype/myalgorithm_v50_spill.py.

### ★★★ v51: capacity-feedback spill (local greedy → global optimal) (2026-07-12)
사용자: spill 사고를 한 단계 업그레이드. v50 spill은 과포화 초과분을 **먼저 온 놈이 밀려나는**
지역(greedy) 결정이었음 → CP-SAT에 **실현용량을 피드백**해 어느 블록을 뺄지 **전역 최적**으로.

**메커니즘 (`_exact_reassign` Benders 루프 내부, SPILL=1):**
- 각 라운드: CP-SAT(cap_eff) → ext → `_spill_realize`(6-order best-of) → best 유지.
- **실현용량 피드백**: spill 결과에서 각 베이의 실현 peak 면적을 측정, 과포화 베이(assigned peak >
  realised peak)의 capf를 그 실측치로 조임(monotone, 0.30 floor) → `continue`로 재풀이.
- CP-SAT가 realistic 용량 하에 **min-Z3 배정**을 스스로 선택 → greedy보다 싼 spill. 라운드 간 best-of
  (라운드는 overshoot 가능).
- **핵심 통찰**: 면적최적 배정(최저 asgZ3)이 실현엔 최선이 아님 — asgZ3 더 높아도 덜-과포화라 실제
  obj가 낮은 배정이 존재(prob_20 asgZ3 235→399인데 obj 105k→92k).

**prob_3 회귀와 수정 (never-worse 복원):**
- 순수 feedback는 `continue`가 `_smallright`를 건너뛰어 **seed 기반 SA-repair 경로를 굶김** → prob_3
  +8.8% 회귀(seed-favorable 소형 인스턴스).
- 수정 3종: (a) **round-0는 항상 `_smallright` 실행**(`_bit>=1`에서만 continue) → SA-repair seed 확보;
  (b) spill 켜지면 `Z1<=0 break` 비활성 → feedback 라운드 계속; (c) round-0 `_smallright`를 **rb=3s
  캡** → 소형은 seed 얻고 대형은 drop 후 feedback로 낙하(예산 보존); (d) seed를 spill에서도 설정.
- SP=0 대비 검증: **모든 인스턴스 never-worse** — prob_11 −40%, 14 −33%, 13 −27%, 18 −25%,
  20(P3) −17%, 9 −8%, 16 −7%, 3/4 동일, 5 노이즈. 저밀도 합 **−18%**, 고밀도 27/38/40 바이트동일.
- **P3(=prob_20): v48 채점기 149620 → 111640 (−25%).** (단독 in-situ에선 91.7k지만 6워커 부하 하
  exact 예산에선 미도달 — P3는 최대 인스턴스라 feedback 라운드가 부하에 컷.)

**기각(정직): C++ `find_best_placement`** — 5× 빠르나 블록 흩뿌려 파편화 → spill 품질 +28~98% 악화.
bottom-left first-fit이 연속 빈공간 보존이 핵심(구축 FBP 기각과 동일 교훈). Python spill이 1.3s로
충분히 빨라 진짜 레버는 best-of order 확대(2→6).
산출물: submit_v51.zip(.so/utils=v48 동일), prototype/myalgorithm_v51_feedback.py.

**v51 저밀도 전수 검증 (prob_1~20, SP=0 vs v51 @90s, 사용자 요청):**
개선 13개: prob_11 −37.8%, 20(P3) −28.1%, 13 −26.9%, 17 −23.4%, 12 −22.4%, 15 −21.4%,
14 −18.1%, 18 −14.0%, 6 −13.7%, 10 −11.4%, 16 −9.8%, 9 −7.8%, 5 −5.2%.
flat 5개(작은 저-Z3): prob_1/2/3/4/8 (±0.1%). 노이즈 플래그 2개(<1%, 분산 내): prob_7 +0.9%,
prob_19 +0.3%. **진짜 회귀 0. 저밀도 합 −16.1%.** 미검증이던 15/17도 큰 승자 → 숨은 seed형 회귀
없음 확인. 고밀도 27/38/40 바이트동일. => v49식 사고 리스크 없음(SA 미변경 + best-of never-worse +
고밀도 바이트동일).

### ★★★★ v52: per-worker mode diversity — P3 sub-100k (149620→~91k, −39%) (2026-07-13)
사용자: sub-100k엔 파이프라인 feedback 수렴을 근본 개선하자 → 메커니즘 재이해로 돌파.

**메커니즘 재이해 (핵심 3발견):**
1. **exact/capacity-feedback는 결정론적** (같은 인스턴스 r1=r2 바이트동일) → 4워커가 **동일 결과 중복
   계산 = 병렬성 낭비.**
2. **exact는 mode별 고정점에 plateau** (알고리즘-제한, 컴퓨트 아님): standalone 예산 16/24/32/48s에서
   seed모드 102770 고정, feedback모드 91741 고정 (dl↑해도 불변).
3. **prob_3 fix(round-0 _smallright)가 spill-favorable(prob_20)의 feedback 궤적을 교란** → 고정점을
   91.7k→102.7k로 올림. 즉 한 mode로 두 인스턴스 유형(seed형/spill형) 동시 최적 불가.

**해법 = per-worker mode+budget 분화:**
- exact에 `mode` 파라미터: "feedback"(round-0 _smallright 스킵, 순수 capacity-feedback → spill형 91.7k)
  vs "seed"(round-0 _smallright로 SA-repair seed → prob_3). 두 mode는 **서로 다른 지역최적**으로 수렴.
- **feedback 워커(짝수 id): SA-stage1 작게(0.1) + exact 큰 예산(45s, 14라운드)** → 파이프라인 경합 하
  에서도 feedback 수렴(경합으로 16s 실효 부족했던 게 원인). **seed 워커(홀수 id): 정상**(SA 0.5, 16s).
- best-of across workers가 인스턴스별 승자 채택. **never-worse**(중복 워커를 탐색으로 전환, seed 후보 보존).

**검증(전수 SP=0 대비):** **P3(prob_20) 151463→91701 (−39.5%, sub-100k!)**, prob_14 −36%, 13 −31%,
11 −30%, 12 −23%, 15 −22%, 17/18 −20%, 5 −19%, 6 −14%, 9 −8%, 16 −9%, 10 −6%, 19 −5.5%, 7 −0.3%,
1/2/3/4/8 flat. **20개 전부 never-worse, 저밀도 합 −19.9%.** 고밀도 27/38/40 **격리 실행 v51=v52=바이트
동일**(스윕 중 27의 편차는 HD ALNS 타이밍 분산, 코드 diff로 HD 경로 v51 동일 확증).

**기각(정직):** 예산 rebal 단독(~105k 바닥), 워커 축소(NPR=2=4, 1은 악화), C++(품질).
**P3 궤적: v48 149620 → v49 176030(회귀) → v51 115550(spill+feedback) → v52 ~91k(per-worker 수렴).**
산출물: submit_v52.zip(.so/utils=v48 동일), prototype/myalgorithm_v52_perworker.py.

---

## 고밀도 P4/P5 headroom 조사 — 크레인 진단 확증 + 배치-스코어링 소진(정직한 음성 결과)

**질문(사용자):** P4/P5는 다른 팀이 더 줄임. obj≥100만대 고밀도를 공격적으로 탐색, 똑똑한
스코어링/패널티 연구.

**진단(hd_probe.py, Z1-지배 인스턴스 전수):** 저밀도 P3와 **동일한 병(다른 축)**.
- P3(저밀도): 베이 ~80% 참, **Z3/면적** 과적 → spill+feedback로 해결(v50→v52).
- P4/P5(고밀도): **peak 베이 점유율 63~71%(≈65%)뿐인데** 40~72% 블록이 대기.
  peak union-2D/cap: prob_23 64-66%, 30 64%, 39 63-66%, 33 64-68%, 27 63-67%, 38 70-71%.
  최악 대기 블록 top25 중 **0/25가 단일 로컬무브로 회복 가능** → 전역 배열 문제(단일 배치 아님).
- 결론: 고밀도 대기 = **면적 아님, 크레인 하강(descent) 접근성 제약**. 65% 참는데 못 내려서 대기.

**크레인-스코어링 실험(craneshadow 모드):** 엔진 배치는 이미 성숙한 best-of 모드군(bigleft,
leftbottom, diagonal, corners, coreperi, prefaware, flat_bl)인데 **전부 2D bbox 높이 h로 스코어링,
누구도 z-레이어 수(크레인 그림자의 실제 원인)를 안 봄.** → 신규 craneshadow: z-tall(>1레이어,
이 인스턴스들 ~80%) 블록을 베이 벽에 붙여 그림자를 외곽에 정렬, 내부를 하강 통로로 유지.
env CRANESHADOW/CSPRIMARY/CRANEPEN 게이트(기본 OFF).

**결과 — 배치 스코어링은 60s 예산에서 소진(음성):**
- **구성 품질(격리, step=1, ALNS 없음, 결정론):** craneshadow는 **prob_39 단독 승**(Z1 473 vs
  bigleft 500, −5.4%). prob_27 2위(1588 vs 1564). prob_23/30은 leftbottom 승. → 정당한 모드지만
  기존 포트폴리오가 나머지 커버.
- **풀 파이프라인(clean A/B, TL=60/90, 단일순차):** CRANESHADOW 0 vs 1이 **5개 인스턴스 전부
  바이트 동일**(prob_40=1989054 기지값, prob_38=34512341 기지 천장). craneshadow tail은 4번째라
  60s에 예산 못 받아 미실행. **ALNS가 구성-품질 격차를 이미 메움**: prob_39 bigleft구성(8.2M)+ALNS
  →7843733 < craneshadow구성(7.88M). 즉 엔진은 60s에 **패킹 수렴**.
- (주의) 초기 TL=12 prob_27 −48% "승"은 **3개 A/B 동시실행 코어경합 아티팩트**였음(clean 재현 실패).

**결론:** **P4/P5 병목은 배치 위치가 아니라 시간축/시퀀싱 탐색.** 65% 참는데 대기 = 이 그리디-디스패치
+ 로컬서치 엔진의 크레인-제약 최적점. 다른 팀의 headroom = Z1/크레인용 전역 재최적화(Z3의 CP-SAT
spill에 대응하는 시간축 버전)에 있음. 배치-스코어링 레버는 여기서 소진.
**조치:** 실험 훅 전부 되돌려 엔진 == v52 정확히 유지(게이트 OFF라 애초 프로덕션 영향 0).
산출물: scratchpad/hd_probe.py, hd_diag.py, cs_construct.py, cs_ab*.sh. **다음 레버 후보 = 크레인-인지
파괴/삽입 ALNS 또는 시간축 CP 서브모델(하강-클리어런스 제약).**

---

## P4/P5 크레인 headroom 정밀 계측 + 크레인-인지 탐색 시도(2차 음성, 그러나 여지는 실재)

**핵심 계측 — 크레인이 Z1의 36~68%를 차지(풀 엔진, 60s, 동일 예산):**
블록을 1레이어로 평탄화(크레인 물리 제거)해 같은 엔진으로 crane ON vs OFF 비교:
| inst | ON Z1 | OFF Z1 | 크레인비용 | %Z1 | wZ1 |
|---|---|---|---|---|---|
| prob_23 | 174 | 56 | 118 | 68% | 1,599,962 |
| prob_30 | 161 | 62 | 99 | 61% | 1,319,967 |
| prob_27 | 1684 | 1084 | 600 | 36% | 7,999,800 |
| prob_39 | 479 | 278 | 201 | 42% | 2,679,933 |
→ **우리 최고 엔진조차 크레인 제약 때문에 Z1을 36~68% 더 냄.** greedy 계측도 44~45% 일관.
여지(headroom)는 **실재하고 크다.** (단 crane-OFF는 제약 소멸의 이상적 하한 = 도달 불가 상한.)

**시도1 — 크레인-인지 destroy 오퍼레이터(ALNS):** delayed+tardy 블록의 대기창 [release,entry)
동안 베이를 채운 incumbents(tall caster 우선)를 evict하고 그 블록을 priority로 재삽입해 하강
통로 확보. 기존 blockers_for는 '현재(늦은) 위치'의 공간중첩만 봐서 이 move 표현 불가.
env CRANEDESTROY 게이트.
- **결과: 6개 Z1-heavy 인스턴스 전부 바이트 동일(CD 0=1).** 파일-카운터로 확인시 오퍼레이터는
  **182회 발화**하지만 **모든 trial이 SA/best-of에서 기각.**
- **원인 = 그리디 repair 하에서 크레인 지연 보존:** b의 통로를 열려고 incumbents를 쫓아내면 b는
  일찍 들어가지만 쫓겨난 블록들이 (같은 크레인 제약으로) 일찍 못 앉아 그만큼 tardy → net 0.
  로컬 destroy-repair는 지연을 **재배치**할 뿐 crane-OFF 전역 배열에 도달 못 함.

**결론(2차 음성, 단 여지는 실재):** 60s 예산에서 P4/P5 크레인 여지는 **볼트-온으로 회수 불가**:
(1) 배치 스코어링=기존 모드와 중복, (2) 로컬 destroy-repair=지연 보존으로 기각, (3) HD는
construction이 예산 소진해 search 여력 자체가 희박(대형 n=250 구성 95~104s). 회수하려면 **evict된
집합을 크레인-인지로 *동시* 재배치**(destroy + tall→벽 동시 repair)하거나 **하강-클리어런스 제약을
가진 전역 CP/MIP 시퀀싱**이 필요 = 대형 재설계, 페이오프 불확실. **v52가 여전히 최선 제출.**
산출물: scratchpad/{flat_run.py(크레인 ON/OFF 계측), nocrane_lb2.py, hd_probe.py}.

---

## 세션 종합 (P4/P5/P3 심층조사) — 중요 발견 5가지

**1. ⭐ grader 머신이 로컬 컨테이너보다 ~2배 빠름.**
prob_20(P3 프록시) TL sweep: 로컬 60s=177111, 120s=105274, 200s=91120. grader 60s=114950
≈ 로컬 ~110s. 즉 **grader 60초 ≈ 로컬 30초**. **모든 로컬 60초 측정이 grader보다 저성능** —
로컬 A/B 해석 시 반드시 감안.

**2. P3 프록시 미스매치 (로컬이 grader 과대평가).**
v48: 로컬 prob_20=151463 ≈ grader P3=149620 (일치, 좋은 프록시). BUT v52: 로컬 91701(격리)
/177111(shipped 60s) vs grader 114950. v52 P3는 **compute-bound** — 로컬 sub-100k는 긴시간
격리수치였고 shipped 60초엔 안 나옴. grader는 149→115k로 진짜 개선(−23%)했지만 로컬(−40%)만큼은 아님.

**3. 크레인 재배치/배정 = exact로 전멸(≈0). v52는 HD 프록시서 국소최적.**
step3(윈도우 CP-SAT), step3b(방향성-정확 크레인 모델), step3d(cross-bay 자유배정 Gurobi) —
전부 크레인 ON에서 개선 ≈0 (증명된 OPT). crane-OFF(36~68% "여지")는 블록이 서로 뚫는
실현불가능 완화의 착시. 배정 area-MIP는 v52보다 나쁨. → 국소 exact는 basin 탈출 불가.

**4. 친구 P4=320만(우리 390만) = 빔(위치탐색, 바텀레프트 안씀). 우리 P6가 친구보다 우위.**
빔이 P4/P5 레버 확정(친구 real-grader 증거). BUT 빔 프로토타입 5개 전부 v52보다 8~22배 나쁨 —
원인: 엔진 construction(place_custom, 이벤트드리븐, free-span, ALNS)을 밖에서 재현 불가.
find_best_placement(fallback)은 fragmentation. 제대로 하려면 place_custom in-place 빔 대수술
(대공사) 또는 친구 파이썬 코드 이식. 순서탐색(squeaky-wheel)은 위치 안 바꿔서 부분만.

**5. Gurobi(WLS, token.gurobi.com 화이트리스트로 활성화) = 이 문제엔 무효.**
크레인 재배치 ≈0(솔버 아닌 물리 한계). 저밀도 배정 MIP은 CP-SAT 0.57s/Gurobi 0.17s 둘다
<1s 같은 최적 → 병목 아님(진짜 병목=spill 기하 realization, Gurobi 무관). 제출 서버엔 Gurobi
있음(폴백 필수).

**메타 교훈:** compute-bound + 머신 2배차 + 타이밍의존 → **로컬 최적화가 grader로 신뢰전이 안 됨**.
앞으로는 "안전 변경 → 제출 → grader 측정" 사이클만 신뢰. 로컬 무한분석은 오도.
산출물: scratchpad/{crane_primitive,step1_profiler,step2_graph,step3*,mip_bench,beam*,p3tl}.py

---

## 빔 대수술(A) 시도 — place_custom top-M 재사용, 근데 이벤트드리븐 구조가 병목

**목표:** 얕은 그리디→국소최적 문제를 "결정적 깊은 빔"으로. 원칙: 엔진의 강한 place_custom을
그대로 재사용(밖에서 약하게 재현 금지).

**구현:** place_custom에 topm 파라미터 추가(점수 상위M 반환, topm=None시 바이트동일). 그 위에
순차 빔 루프(K상태, 블록마다 top-M 분기, obj-so-far로 prune). env BEAMK 게이트.

**결과(prob_30, P4-proxy, DL=90):**
- greedy: obj=3617004 Z1=208 (16s)
- 빔 K=8 M=4: obj=7838055 Z1=527 (123s) ← 여전히 나쁨(2배), 느림

**진전 있었음:** 약한배치빔 8~22배 → place_custom재구현빔 8배 → **진짜 place_custom+순차빔 2배.**
place_custom 재사용이 확실히 개선. **근데 아직 짐 — 이제 병목은 이벤트드리븐 dispatch 구조 자체.**
greedy _smallright_construct는 매 시각 pending 전부를 튜닝순서+free-region으로 처리(멀티블록/틱).
내 순차빔은 블록 하나씩이라 그 구조를 깸.

**결론:** 엔진 construction 품질 = 여러 튜닝레이어(place_custom점수 + 이벤트드리븐dispatch +
free-region + 모드 + ALNS)의 합. 충실한 빔 = **이벤트드리븐 루프를 빔으로**(각 상태가 자기 이벤트
상태 유지, 틱내 멀티블록 분기) = 훨씬 큰 다세션 수술. WIP: prototype/myalgorithm_beam_wip.py
(place_custom top-M 인프라 재사용 가능). shippable은 v52 유지.

**세션 최종 상태:** 얕은탐색→국소최적 진단은 P3(Z3)·P4/P5(Z1) 공통 확증. 처방(결정적 깊은빔)도
확정. 근데 자력구현은 엔진의 다층 튜닝 재현 난제로 다세션 규모. 현실 경로: 친구코드 이식 or
이벤트드리븐 빔 다세션 빌드 or v52 확정.

---

## feat_w 순서방향 A/B (prob_30, P4-proxy) — 결정적 음성결과

**가설:** 기하 방향모드(bigleft 등)는 풀솔버에서 수렴(diminishing returns)이지만, dispatch **순서**
(feat_w)를 바꾸면 강한 place_custom 배치는 재사용하면서 construction이 찾는 **basin**이 달라져
P4/P5에서 이길 수 있다.

**방법:** `_smallright_construct(mode=bigleft, feat_w=<dict>)` 10방향, 전부 DL=45 동일, 순수
dispatch순서만 변수. feat_w 미변경 v52로 검증(엔진수정 0).

**결과(prob_30, 150블록):**
| 방향 | obj | Z1 | Z2 | Z3 |
|---|---|---|---|---|
| **rank(base)** | **3,617,004** | **208** | 4935 | 4120 |
| area+slack | 3,857,217 | 225 | 2923 | 4228 |
| area | 4,203,621 | 249 | 4526 | 4328 |
| hgt+area | 4,254,000 | 252 | 3021 | 4410 |
| hgt | 4,319,399 | 271 | 2439 | 3482 |
| due+hgt | 4,442,430 | 262 | 5196 | 4642 |
| due | 4,586,537 | 285 | 2958 | 3874 |
| proc | 4,771,360 | 288 | **264** | 4652 |
| work | 4,949,966 | 314 | 1651 | 3784 |
| slack | 5,727,407 | 363 | 1182 | 4414 |

**결론:** **base rank(big+urgent)가 obj·Z1 둘 다 압도적 최소**, 모든 feat_w 단일특징 재정렬은 6~58%
악화. 일부는 Z2/Z3 국소개선(proc→Z2 264, hgt→Z3 3482)하지만 Z1이 그 이상으로 폭발해 총obj 손해.
→ **dispatch순서 레버는 P4에서 무효.** 기본 rank가 이미 강한 basin이고, 단일특징 재정렬은 그 basin을
교란만 함. 병목은 dispatch순서가 아니라 **place_custom의 얕은 방향탐색 자체**(앞선 진단 재확증).
shippable v52 유지, 엔진변경 없음.

---

## 내부 빔 최소검증 (prob_30, P4-proxy) — **그리디를 이김 (가설 확증)**

`_smallright_construct` 이벤트루프 내부에 최소 빔 이식: place_custom에 topm 추가(byte-identical off),
K개 부분packing 유지, 블록결정마다 top-M 분기 → 커밋비용(w1·지연+w3·pref)으로 K prune. E는
상태별 clear_all+재적재(현재present 블록만, ex>cur)로 feasibility 충실. 블록 1개/확장 → 동일깊이
비교 공정. (n=150<200이라 free-region OFF 경로.)

**결과(prob_30, bigleft):**
| | obj | Z1 | Z2 | Z3 | 시간 |
|---|---|---|---|---|---|
| greedy | 3,617,004 | 208 | 4935 | 4120 | 16s |
| beam K4 M2 | 3,720,874 | 214 | 3003 | 4278 | 108s |
| beam K6 M2 | 4,014,379 | 235 | 3881 | 4328 | 200s |
| **beam K8 M3** | **3,540,693** | **205** | **2557** | 3986 | 243s |

**결론:** K8·M3가 그리디 **-2.1%**(Z2 4935→2557 반토막). **빔이 그리디를 이긴 최초 사례.** 얕은탐색→국소
최적 진단의 처방(결정적 깊은 분기탐색)이 실제로 유효함을 엔진 내부에서 확증. 단 느림(243s 로컬≈grader
120s), 작은 K/M는 손해(어설픈 prune이 좋은 basin 폐기). place_custom 배치품질 재사용이 핵심 — 밖에서
재구현한 예전 빔(8~22배 악화)과 정반대. shippable v52 유지(BEAMK env-gate, 기본 off).

---

## 군집확장배치(cluster, max-contact) 모드 A/B (prob_30)

place_custom 새 모드 `cluster`: big블록을 bottom-left 대신 **기존 블록bbox+벽과 접촉(공유 엣지길이)
최대화**로 배치 → 한 덩어리로 뭉쳐 큰 연속 빈 구역 하나 남김(크레인 통로 확보 의도). 접촉=벽 접함 +
present bbox와 x/y 인접 겹침길이. tiebreak bottom-left. best-of 변형(min 유지→퇴보 불가).

| | obj | Z1 | Z2 | Z3 | 시간 |
|---|---|---|---|---|---|
| bigleft greedy | 3,617,004 | 208 | 4935 | 4120 | 16s |
| cluster greedy | 3,734,188 | 224 | **2399** | **3690** | 15s |
| cluster beam K8M3 | 4,321,270 | 266 | **1473** | 3844 | 272s |
| bigleft beam K8M3 | **3,540,693** | 205 | 2557 | 3986 | 243s |

**결론:** 군집확장은 **Z2(균형) 반토막·Z3(선호) 개선**하지만 **Z1(지연)을 악화** → w1·Z1이 지배하는
P4에선 총점 손해. beam을 얹으면 더 나빠짐 — cluster의 top-M 후보가 전부 '빽빽한' 위치라 beam이
빽빽함 변형 중에서만 고르게 되고, 빽빽함이 크레인 하강을 막아 지연 증폭. → **군집확장은 P4 레버가
아님**(Z2/Z3 지배 인스턴스용 best-of 변형 가치는 있음). **P4 레버는 bigleft+beam(-2.1%).**

**단, 예산 현실:** bigleft+beam은 K8M3(243s 로컬≈grader ~130s)에서만 이김. 예산내(K4M2, 108s)는
그리디에 짐. 즉 **빔의 승리를 shippable로 만들려면 속도**(E clear_all+재적재가 병목)가 다음 과제.

---

## P3 크레인통로 가설 검증 — 유저 직관 확인 + 빔의 prune 한계 발견

**유저 질문:** P3도 너무 빡빡하게 넣어 크레인통로 보존이 안 돼 막히나?

**P3 물리(prob_20, 300블록):** deadline 느슨 → **Z1=0**. obj = w2·Z2 + w3·Z3, 그중 **Z3가 ~83%**
(125·964 vs 6·4116). 즉 P3는 "어느 bay(선호)"가 전부고 "얼마나 빡빡"은 부차적.

**모드 A/B(prob_20 greedy):**
| mode | obj | Z2 | Z3 |
|---|---|---|---|
| bigleft | 1,358,564 | 4844 | 10636 |
| cluster | 1,347,329 | 5159 | 10531 |
| **prefaware** | **145,196** | 4116 | **964** |

→ **cluster(빽빽)는 Z3 거의 안 움직임**(10531 vs 10636). tightness는 bay 안 문제고 P3 비용은 bay 선택.
**진짜 레버는 prefaware(선호 bay 우선)** — obj 9배 개선. 유저 직관("통로 막혀 spill")은 **맞지만**,
올바른 표현은 "선호 bay 크레인수용량 부족→spill"이고 해법은 tightness가 아니라 **선호-bay-aware 배치**.

**prefaware + beam 검증(prob_3, 100블록):**
| | obj | Z3 |
|---|---|---|
| prefaware greedy | 74,820 | 224 |
| prefaware beam K8M3 | 74,820 | 224 |
| prefaware beam K12M4 | 74,820 | 224 |

→ **빔이 완전 무효(byte-동일).** 이유 규명: prefaware의 top-M 후보는 전부 선호 bay 안(penalty 동일)
→ **커밋비용이 전부 동점** → 빔 prune이 위치들을 구분 못 함 → 그리디 재현. 빔이 P4에서 이긴 건 위치마다
**커밋 Z1(지연)에 즉각 gradient**가 있었기 때문. P3의 Z3는 선호 bay 안에선 gradient 0.

**결론:** 빔은 **커밋비용에 gradient 있는 곳(P4 Z1)에서만** 이기고, 없는 곳(P3 Z3)은 그리디 재현.
P3를 이기려면 prune에 **방(통로) lookahead 휴리스틱**(배치 후 선호bay 잔여 연속공간 등)이 필요 —
현 커밋비용 prune으론 불가. + 배송 P3경로는 이미 pref_reassign(CP-SAT bay 재배정)으로 Z3=609 달성
(단일패스 964보다 우수). 194(area-LB)까지 gap은 강제배정 실패로 증명된 크레인-비실현성.

---

## 아이디어 1 검증 — 하강통로 스카이라인 value로 빔에 gradient 부여 (P3 최초 개선)

**통찰:** 우리 배치모드는 전부 2D(넓이)인데 결합제약은 2.5D 크레인 하강통로. 스카이라인이 idea3(빔 value)의
빠진 조각을 채움 — "배치 후 남는 **최대 연속 빈 사각형**(=열린 하강통로 면적)"을 빔의 tiebreak value로.
커밋비용 동점(P3 선호bay 내부)일 때 통로 보존 위치를 골라 spill↓.

**구현:** `_lfr(rects,W,H)` = 16×16 coarse grid 최대 빈 사각형(histogram O(R²)). 빔 child마다 room=Σ_bay
_lfr(present after placement). prune key `(cost, -room, -np)`. env SKY=1 게이트(off시 기존 빔과 동일).

**결과(prob_3, prefaware, 100블록):**
| | obj | Z2 | Z3 |
|---|---|---|---|
| greedy | 74,820 | 4122 | 224 |
| beam K8M3 (no sky) | 74,820 | 4122 | 224 |
| **beam K8M3 +SKY** | **73,160** | 4031 | 219 |

→ **P3에서 처음으로 그리디를 이긴 구성.** no-sky 빔은 무효(동점 구분 못함)였는데 SKY value가 gradient를
줘서 Z3(spill)·Z2(균형) 동시 개선(-2.2%). 아이디어1(크레인-native 배치)+아이디어3(빔 value)이 한 방에
검증. 통로보존→선호bay에 더 많이 앉음이 실증됨. (효과크기 sweep + P4 무해성 확인 진행중.)

---

## 아이디어 2 검증 (tall-first z-layer dispatch) + 스카이라인 효과크기 sweep

**z-층수(zlay) 특징 추가** (feat_w에 "zlay"=층수 rank, orientation-invariant). 층수는 {1,2} 이진.
mode=prefaware greedy, dispatch만 tall-first.

| inst | rank(base) | zlay-first | SKY-beam |
|---|---|---|---|
| prob_1 | 24105 | 33999 (+41%) | **9779 (-59%)** |
| prob_3 | 74820 | **72460 (-3%)** | **73160 (-2%)** |
| prob_4 | 93279 | **42296 (-55%)** | **57718 (-38%)** |
| prob_2 | 6620 | - | 8780 (+33%) |
| prob_20(P3size) | 145196 | 182036 (+25%) | (빔 300블록 too slow) |

**결론:** 두 아이디어 모두 **크레인-통로 thesis를 실증** — spill 많은 인스턴스(prob_4)에서 -38~-55%
대박. 하지만 **둘 다 비일관**(prob_3/4 win, prob_1/20 lose) → best-of 변형으로만 안전(min 유지→무regress).
greedy는 결정적 확인(prob_3 x2 동일).

**핵심 caveat:** **실제 P3 크기(prob_20, 300블록)에선 둘 다 이득 없음** — zlay는 +25% 악화, SKY-beam은
300블록서 너무 느림. 즉 100블록 저밀도엔 통함이 증명됐지만 300블록 P3로 **아직 전이 안 됨**.

**언락(다음):** SKY value는 **빔이 필수가 아님** — `_lfr`(통로면적)을 place_custom **greedy 배치모드**로
직접 쓰면(각 후보를 잔여통로로 스코어) 300블록도 빠르게(그리디 27s) 스케일하고 통로보존 효과를 얻음.
= 아이디어1의 진짜 shippable 형태("똑똑한 cluster" greedy mode). 다음 과제.

---

## greedy 스카이라인 모드 실패 — 통로보존은 lookahead(빔) 필수, 탐욕은 myopic

`_lfr`을 place_custom greedy 모드(skyline/skypref)로 직접 사용 → **참패**:
| inst | prefaware | skypref | skyline |
|---|---|---|---|
| prob_1 | 24105 | 255243 | 494655 |
| prob_4 | 93279 | 343001 | 678440 |
| prob_20 | 145196 | incomplete 89/300 | incomplete 102/300 |

**Z2는 크게 좋아지는데(산개→부하균형) Z3 폭발**(78→2464). 이유: **탐욕적 per-placement 통로최대화는
myopic** — 지금 큰 빈사각형 남기려 블록을 흩뿌림 → 레이아웃 파편화 → 나중 블록 spill 폭증. 빔이 통했던 건
통로가 **시퀀스 lookahead 탐색 안의 tiebreak**였기 때문(동점 Z3 후보 중 선택), 탐욕 primary 목적이 아님.
+ 300블록서 _lfr/후보 비용으로 미완성(느림).

**구조적 교훈:** 통로보존 레버는 **빔(lookahead) 없이는 무효**. 단순 모드추가로는 안 됨. 그리고 빔은
150블록 OK, 300블록(실제 P3) too slow. → **실제 P3 공략 = 빔을 300블록에 스케일**(비트맵 feasibility로
가속, 또는 spill난 블록집합만 타겟 LNS-빔)이 남은 유일 경로. 소형 저밀도(P1/P2?)엔 SKY-빔 best-of가 유효.

---

## 아이디어 2 재검증 (충실한 버전) — tall-first를 tiebreak로 = 공짜 승리, 무regress

첫 테스트(전역 순서 반전)는 "급하고 큰 것 먼저" rank를 파괴해 비일관적이었음. **유저의 실제 통찰은
"공존집합 안에서만 키 큰 것 먼저"** → rank primary 유지 + tall-first를 gentle tiebreak로.
`feat_w={due:1,area:1}`==base rank 정확 동일이므로 +zlay*ε가 딱 그 형태.

| inst | base | +tall ε=0.1 | ε=0.3 | ε=0.5 |
|---|---|---|---|---|
| prob_1 | 24105 | **9779 (-59%)** | 9779 | 17707 |
| prob_3 | 74820 | 74820 (중립) | 74820 | 74820 |
| prob_4 | 93279 | **71164 (-24%)** | 71164 | 92589 |
| prob_20 | 145196 | 145196 (중립) | 159037 | 174352 |

**ε=0.1 스위트스팟: prob_1 -59%·prob_4 -24% 승, prob_3/20 완전 중립(무regress).**
- **prob_1 -59%(9779)는 비싼 SKY-빔 결과와 정확히 동일** — 19s 빔이 찾은 걸 2s 공짜 dispatch tiebreak로.
- 통로보존 이득의 **저렴한 형태**(빔 없이 순서만). ε 키우면 rank 침범→악화(0.3+ prob_20).
- 한계: prob_20(실제 P3 크기) 중립(이득 없음). best-of 변형으로 완벽(win시 win, else fallback).
- 함의: **P1/P2가 소형 저밀도면 직접 도움**. shippable 통합가치 있는 첫 저비용 레버.

---

## 날카로운 crane-criticality dispatch (critC) — 소형 대박, P3는 크레인-floor 확정

**측정 버그 발견/수정:** 멀티인스턴스 테스트가 `_smallright_construct` 직접호출로 algorithm()의
캐시클리어를 건너뜀 → 기하캐시(block_id 키, 인스턴스 무관)가 인스턴스간 오염. prob_20(block_id 0-99
재사용)이 특히 오염. **캐시클리어 후 재검증(clean):**

| inst | base | rank+critC ε=.1 | critC-first |
|---|---|---|---|
| prob_1 (100) | 24105 | 9779 (-59%) | **2065 (-91%!)** |
| prob_4 (100) | 93279 | **40029 (-57%!)** | 54430 (-42%) |
| prob_20 (300,P3) | 145196 | **145196 (정확 중립)** | 225478 (악화) |

**critA(면적×층수)는 약함, critC(선호bay 혼잡도=내 선호bay를 시간겹쳐 경쟁하는 블록 총면적)가 핵심.**
= "most-constrained-first"의 날카로운 형태(선호bay에서 밀려날 놈 먼저 자리잡기). tall(-24%)보다 훨씬 큼.

**결정적 결론 — P3는 dispatch로 못 줄임:** prob_20이 critC에 **정확히 무반응**(145196 불변), critC-first는
악화. 앞선 증명(강제배정 609→1085 악화, area-LB 194 도달불가)과 합쳐 **P3의 Z3는 크레인-실현가능 floor**
확정 — 선호bay가 크레인 하에서 물리적으로 초과구독이라 어떤 순서도 더 못 넣음.

**함의:** critC-first는 **소형 저밀도(P1/P2가 100블록급이면)에 -57~-91% 대박** best-of 변형(무regress:
prob_20은 base로 fallback). P3(300블록)엔 무효. + 캐시버그가 앞선 P4 greedy 불일치(3617004 vs 3370924)도
설명 — 오염이었고, 단일인스턴스 P4 빔 win(-2.1%)은 clean.

---

## P3 실제경로 정밀분석 (프록시 실수 정정 후) — 크레인 floor 6중 확증

**중대 정정:** 이전 critC/skyline/tall 실험은 `_smallright_construct`(P6-gated, P3 미사용) 대상이라 무의미.
실제 `algorithm()`의 저밀도 경로는 construction+ALNS+**CP-SAT/Benders bay 재배정**+SA. prob_1 실제=1499
(프록시 24105 아님). 이하 전부 **실제 algorithm() clean 단독측정**.

**실제 prob_20(P3) = obj 90230, Z2=2705, Z3=592** (Z3가 obj의 82%). 30k 절감 = Z3 592→~350 필요.

**6중 확증 — P3 Z3는 크레인-실현가능 floor:**
1. **예산 아님:** TL=300(90769) ≈ TL=120(90230). 재배정 수렴.
2. **spill 진단:** 밀려난 39블록 중 회복가능 5개(Z3 23)뿐, **34개 진짜 크레인-full**. 96% 구조적.
3. **게이트 정상:** `_low_density`(Z1비중<0.5)로 P3는 강한 재배정 정상 수신. 게이트 버그 없음.
4. **tall/critC 실현순서 추가:** 무효(예산잠식 소폭 악화).
5. **EXROUNDS↑ Benders:** 효과 없음(수렴).
6. **`_beam_realize`(위치+배정 동시 재최적화, 크레인-통로 K-빔):** spill_realize보다 **나쁨**
   (136725 vs 145864). 최대빈사각형=myopic proxy, 더 못 담음 + Z2 무시.

**"v52 600 감소"의 정체:** CP-SAT+Benders bay 재배정(construction 145k→90k)의 일회성 구조승리.
**이미 수렴** — 같은 메커니즘으론 추가 없음. w1=26667(거대)이라 tardiness 거래도 break-even 불가.

**결론:** prob_20 물리(선호bay 크레인 초과구독)상 30k 절감 근거 없음. 유일한 미검증: 히든 P3가
prob_20과 구조적으로 다를 가능성(측정 불가). 실험코드(모드/특징/빔/_beam_realize) 전부 env/mode-gate,
기본 off → 배포 algorithm()은 v52 불변(prob_20 90230 재확인).

---

## ★ P3 서버 저성능 근본원인 발견 + 수정 (예산 배분 버그) — TL=60에서 -43%

**유저 통찰:** 친구 10만대·최고 8만대인데 우리 그레이더 P3=115k. "서버에서 알고리즘이 잘 작동 안 되는 것"
아니냐 → **정확했음.** 로컬 90k인데 그레이더 115k인 이유 = **재배정이 그레이더 시간예산 안에 수렴 못 함.**

**진단 (프로파일링):**
1. TL 민감도: prob_20 TL=120→90k(수렴), **TL=60→177k(미수렴)**. 그레이더는 60s → 미수렴.
2. 프로파일: `_exact_reassign` Benders 루프의 **80%가 check_feasibility(shapely 기하)** — 후보 랭킹마다
   느린 재검. C++ 엔진이 이미 feasible 보장하는데도.
3. **결정적 버그(DBG 계측):** ALNS(24s)와 강한재배정tail(59.6s) 사이 **중간 폴리시 5단계**
   (_shift_forward/_temporal_share/_balance_load/_swap_polish/_pref_reassign)가 `deadline`까지 탐욕적으로
   **35초 먹어치움** → 진짜 레버인 재배정tail이 59.6s에 시작(0.4s 남음) → **아예 안 돌아감.**

**수정 3종 (전부 저밀도 게이트, 고밀도 byte-identical):**
1. **fast-obj:** _spill_realize 후보 랭킹을 check_feasibility→`_objective`(동일 공식, 기하 없음). caller가
   real check로 재검증→안전. Benders ~4-5x 가속(수렴 120s→90s).
2. **fast Benders 라운드:** 수렴 라운드는 3오더×coarse step, 마지막에 full 실현 1회. (feedback 워커만)
3. **★ tail-reserve:** 저밀도에서 중간 5단계를 `_mid_deadline`(post-ALNS 예산의 35%)로 캡 → 재배정tail이
   65% 확보. **워커 패리티 분산**(even=aggressive, odd=원본) → best-of가 never-worse 보장.

**결과 (TL=60, 그레이더 예산, vs 진짜 fr2-start baseline):**
| inst | fr2-start | 수정후 | |
|---|---|---|---|
| prob_20(P3) | 163274 | **92889 (-43%!)** | ★ |
| prob_16 | 47622 | 42840 (-10%) | ✓ |
| prob_13 | 73928 | 73590 | ✓ |
| prob_6/9/19 | - | 동일/노이즈 | 무regress |
| prob_30(P4,고밀도) | 3046457 | 3046457 (불변) | 게이트off |

TL=120에선 여전히 ~90k 수렴. **그레이더(60s, 로컬보다 빠름)에서 P3 115k→~90k 기대** = 유저 목표 근접.
스냅샷: prototype/myalgorithm_v53_p3budget.py (그레이더는 env 없음→기본값이 수정 활성화).

---

## P4 매처리스틱 분해 탐색 (스케줄MIP + 실현기 + 배치MIP) — 벽 규명

유저 방향: 빔 대신 수리최적(Gurobi/CP-SAT) 매처리스틱 분해. Gurobi WLS 작동 확인(13.0.2).

**핵심 진단 — P4는 배치품질이 전부:**
- prob_30 pipeline obj=3046457 **Z1=161** (Z1이 ~70%, w1≈13333). Z1은 TL 60/120/200 전부 161 고정 → 예산 아닌 **품질(지역최적)** 한계.
- 프로파일: 병목이 check_feasibility(P3)와 달리 **shapely NFP 기하**(_candidate_positions).
- **결정적:** realize_hd에 파이프라인 *자기 스케줄*(Z1=161내는 bay+entry) 먹여도 → **Z1=528**. 즉 스케줄 아닌 **위치·회전 배치**가 전부.

**Stage A 스케줄링 MIP (_cpsat_schedule):** 면적완화로 Z1 하한 74(eff0.63)~0(eff0.85) 발견 —
탐욕이 Z1 크게 흘림 증명. **단 실현 불가:** 어떤 실현기로도 크레인하 Z1=444~528 (하한 74 도달불가,
P3의 area-LB 194 도달불가와 동형). 면적완화가 크레인엔 무의미.

**Stage B/유저 배치MIP (Gurobi, cell non-overlap):**
| 창크기 | 격자 | 결과 |
|---|---|---|
| coarse step2 bbox | | 빠름(2-5s)이나 거짓충돌로 4/26 (모델오류) |
| 정확 unit cell K26 | step2 | 100k var, 25s 내 해 없음(intractable) |
| 정확 cell K15 | step4 | 15/15 OPTIMAL (14s) |
| 정확 cell K26 | step3/4 | 해 없음(intractable) |

**결론:** 정확 불규칙-packing MIP는 **≤15블록서만 tractable(그것도 14s), ≥20 intractable** — OR 문헌의
알려진 벽. P4 혼잡창(26 공존)은 단일 MIP로 못 품. 크레인+시간축 추가시 더 악화. **MIP-LNS도 14s/창이라
비현실적.** 유저 아이디어(크레인페널티+촘촘함 목적항)는 방향은 맞으나 이 tractability 벽에 막힘.

**남은 길(다세션):** candidate-column set-packing(격자 아닌 휴리스틱 후보 위치로 var 축소) 또는 NFP기반
MIP 등 영리한 formulation 필요. 또는 P4=161이 통합휴리스틱 floor 인정. P3(-43%, v53)는 확정 성과.

---

## P4 배치MIP 돌파구 — candidate-column set-packing (앞 "벽" 결론 정정)

full-grid MIP(100k var)는 intractable였지만, **블록당 후보 배치 ~30개만 생성**해 MIP가 non-overlap
부분집합 선택 → **var 100k→8k**:
| K | var | 결과 |
|---|---|---|
| 15 | 4575 | 15/15 OPTIMAL 2.9s |
| 26(전체 혼잡창) | 8026 | 26/26 배치(gap~0) 20s |
| 26 +촘촘함항(λ0.02) | 8026 | 26/26 gap0.007 |

**즉 배치MIP가 tractable해짐 — 유저 방향의 기초 성립.** 촘촘함 목적항도 바로 결합됨.

**남은 다세션 작업:** (1) 크레인은 개별후보가 아니라 *조합*(하강순서)에 걸리므로 MIP에 크레인 제약/페널티
모델링 or 선택조합 feasibility 체크, (2) 시간축(tardy 블록을 창에 포함해 Z1 감소 목표), (3) MIP-LNS 루프
(혼잡창 떼고 재최적화 반복), (4) 파이프라인 161 실제로 깨는지 검증. 20s/창은 후보수↓·warm-start로 가속 여지.
기초는 섰고, 이 위에 크레인+시간+LNS 얹는 게 다음 단계.

## P4 배치MIP 병목 규명 — 전체재packing이 문제, LNS창은 <1s

Gurobi K=26 로그 분해: BUILD 3s + **Presolve 8.1s(병목)** + root 0.5s + B&B 1노드. 밀집행렬(4022행×9882열
nonzeros 95만) — 촘촘packing 위해 후보 380/blk라 셀-non-overlap 제약이 밀집. 후보 줄이면(116/blk) 21/26만
배치(표현부족), 늘리면(380/blk) 26/26이나 느림 → **전체 재packing 자체가 최악 케이스.**

**LNS창(대부분 고정+소수 재배치) 측정:**
| 자유블록 | 고정 | vars | solve |
|---|---|---|---|
| 4 | 22 | 309 | 0.09s |
| 6 | 20 | 578 | 0.15s |
| 8 | 18 | 1023 | 0.37s |
| 10 | 16 | 1443 | 0.56s |

전부 100% 배치·최적·<0.6s. **병목(밀집 presolve)은 LNS 구조가 회피** — 고정블록=장애물 셀, 변수는 자유
블록만. 60s에 수십~수백 창 가능. 크레인·시간축도 작은 창에만 붙어 여전히 빠름. **배치MIP-LNS tractability
완전 확보.** 다음: 자유창에 크레인 제약 + tardy블록 포함 + obj(지연) → 161 깨기.

## P4 크레인 모델링 — 단순화 통찰 + 두 구조적 난제 규명

**단순화 통찰(유저 질문 답):** 진입순서 고정 시 크레인은 {1,2}층에서 **정확히**: i(나중) vs j(먼저) 공존 →
i.바닥 ∩ j.실루엣=∅ AND i.윗층 ∩ j.윗층=∅ (j≥k 규칙과 일치). 즉 "진입시각 고정"이 시간·하강복잡성을
없애고 정적 셀제약으로 만듦. prob_30: 2층블록 122개 중 44개 overhang → 실루엣 필수.

**구현+엔진검증 → 두 난제 발견:**
1. **셀 rasterization ≠ 엔진 연속기하:** 실루엣 non-overlap(심지어 1-cell 팽창)해도 엔진 stage-2(크레인
   entry) FAIL. 단위격자가 정확 크레인과 불일치(오래전 bitmap 정밀도 벽 재현). → lazy 엔진검증(no-good cut)
   or 정확 NFP 필요.
2. **크레인 시간의존성(더 근본):** 자유블록 b를 옮기면, b보다 **늦게 진입하는 고정블록 k**의 하강이 b 신위치에
   막혀 깨짐. MIP는 자유→고정 회피만 걸고 고정→자유는 안 걸음. 즉 "대부분 고정+소수 이동" LNS가 크레인선
   무효. **유효창 = 시간suffix**(bay에서 시각 T 이후 전부 자유) — 그래야 옮겨도 이전블록 안 깨짐. 단 T 이르면
   블록 많아 커지고, 늦으면 최적화 여지 적음(tension).

**P4 매처리스틱 종합 지도:** tractability는 해결(candidate-column LNS <1s), 하지만 크레인이 (a)기하정밀도
(b)시간의존성 두 벽을 세움. 진짜 빌드 = 시간suffix 창 + lazy 엔진 크레인검증(cut) + 목적(지연). 다세션 연구.
P3(-43% 로컬, 그레이더 115k→105k 실측확인)는 확정 성과.

---
## v54 — 저밀도(P3류) tail-full 예산: 중간 폴리시 단계 스킵 (레버1 가속화)

**동기(user):** "먼저 레버1로 가속화 해보자 cpp로" — P3를 8만 초반대로.
**핵심 발견(프로파일링):** C++ 재컴파일은 불가(ogc_fast 소스 .pyx/.cpp 없음, .so만 존재).
그런데 실제 병목은 C++ 스캔이 아니라 **shapely `check_feasibility`** 였음.
실제 W0(feedback, cpp_engine=True) 프로파일 @TL40:
  - `check_feasibility` 144회 = 10.5s (프로파일 시간의 ~40%)
  - 그중 `_shift_forward` 123회(3.75s) + `_balance_load` 20회(3.16s) = 143회/~7s
  - CP-SAT 4.4s
`_shift_forward`는 Z1(지연) 레버인데 **저밀도는 Z1≈0이라 무의미** — 그냥 예산만 태움.
5개 중간 폴리시 단계가 exact-Benders tail(진짜 Z3 레버)을 굶겨서 60초에 수렴 못함.

**측정(prob_20 = P3 프록시, 로컬 4코어, taskset 격리):**
| 설정 | @60s obj (여러 런) | 평균 |
|---|---|---|
| 기존 기본값(even=0.65) | 107.7k, 110.0k | 108.8k |
| TAILRES=1.0 (중간단계 전부 스킵) | 92.6k, 96.0k, 93.0k | 93.8k |
| 참고: 기존 @120s 수렴바닥 | 93.8k | — |

→ **중간 단계를 스킵하고 tail에 100% 예산을 주면 60초 안에 @120 수렴바닥(93.8k)에 도달.**
prob_20 로컬 @60 **108.8k→94.0k (-14%)**. 전부 Z1=0(feasible).

**적용(never-worse, 가법적):** `_low_density` 게이트 안에서 워커별 3중 다양화 —
worker0 → TAILRES=1.0(순수 tail), worker2 → 0.65(기존), 홀수워커 → 0.0(기존 폴리시).
best-of가 {1.0, 0.65, 0.0} basin을 모두 커버(기존 {0.65,0.0}의 상위집합) → **증명적 never-worse**.
고밀도(Z1share≥0.5)는 `else` 분기(=deadline)로 완전 불변 → P6/prob_30 byte-identical.
검증 @60: prob_20=94.0k, prob_3=48.4k, prob_6=49.3k, prob_11=29.6k (모두 Z1=0).

**기각한 대안:** C++ `find_best_placement` fast-seat(FASTSEAT) — 6배 빠르나(0.10s vs 0.62s)
scatter로 obj +33%(146k→194k), 게다가 realised-capacity 피드백을 오도할 위험 → 미채택.

**남은 것:** 94k는 레버1(수렴)의 천장. 8만대는 레버2(품질: 선호bay 촘촘패킹으로 Z3 바닥 낮추기) 필요.

---
## 레버2 진단 (Z3 바닥) — prob_20(P3 프록시), v54 위에서

**목적함수 분해:** weights w1=26667, w2=6, w3=125. obj=94k(Z1=0)일 때:
  - w2·Z2 = 6×2273 = 13,638 (15%)
  - w3·Z3 = 125×643 = 80,375 (**85% — Z3가 지배**)

**MIP는 진짜 목적함수를 맞게 최적화 중:** 내부 CP-SAT는 `6·Mv + 125·1000·Z3`,
Mv=1000·Z2(U[j]=1000·avg/cap[j]=1000·bay_unit) → `1000·(6Z2+125Z3)` = 1000·진짜obj. 미스캘리 없음.

**핵심: 배정LB ≪ 실현값 (패킹밀도가 병목).** 면적완화 배정최적(실현가능성 무시):
| area-cap | Z2 | Z3 | obj |
|---|---|---|---|
| 1.0 | 3526 | 235 | **50.5k** |
| 0.9 | 2575 | 316 | 55k |
| 0.8 | 2124 | 452 | 69k |
| 실현값(현재) | 2273 | **643** | **94k** |

그러나 이 배정들을 `_spill_realize`로 실제 실현하면 배정과 무관하게 Z3≈700-800으로 튐
(cap1.0→692, cap0.8→715). SA가 그걸 643까지 refine. **어떤 배정을 줘도 realizer가
선호bay에 그만큼 못 넣어서 spill → Z3 바닥이 ~640.**

**bay별 peak 면적이용률 (실현 94k해):**
| bay | dims | nblk | 선호수 | peakUtil | Z3기여 |
|---|---|---|---|---|---|
| bay0 | 136×28 | 75 | 60 | 80% | 246 |
| bay1 | 32×29 | 42 | 62 | 84% | 0 |
| bay2 | 153×15 | 62 | 62 | **75%** | 90 |
| bay3 | 150×27 | 73 | 59 | 84% | 265 |
| bay4 | 58×29 | 48 | 57 | **100%** | 41 |

작은 선호bay(1,2,4)가 꽉 차서 ~50블록이 큰bay(0,3)로 spill → Z3=246+265 집중.
bay2(75%)만 여유 있어 보였으나 **격리테스트: bay2를 그 선호62블록에 전용해도 59/62만 안착**
(3블록은 bay 통째로 + 전 orient + 전 entry시각 자유여도 온타임 안착 불가). = 진짜 크레인 천장.

**수렴 확인:** TL 60→Z3=642, 120→Z3=621 (2배 시간에 21단위). tail 거의 수렴, 바닥 ~615-620.
→ **이 realizer의 실현 obj 바닥 ≈ 90k.** 80k(Z3≈530)는 선호bay에 물리적으로 불가능한
~15블록을 더 넣어야 함 = 크레인-aware 고밀도 패커 필요(이전 세션들이 못 깬 난제).
주의: prob_20은 프록시. 진짜 P3의 바닥은 다를 수 있음(히든이라 직접측정 불가).

**레버2 최종 결론 (3중 확인, prob_20):** 작은 선호bay 최대안착(전용, 검색 총동원):
  - bay1(32×29): 43/62 (261 orders) / 42 (545 destroy-repair) → ~19블록 강제 spill
  - bay2(153×15): 59/62 (모든 검색 동일) → 3 spill
  - bay4(58×29): 53/57 → 4 spill
  - bay0/bay3(큰bay): 선호블록 전부 안착(60/60, 59/59)
합계 ~26블록이 어떤 패커로도 선호bay에 못 들어감 = **진짜 용량/크레인 천장**(greedy 아님).
destroy/repair 수백 iter도 greedy 못 이김. **실현 obj 바닥 ≈ 90k 확정.**
→ 80k는 prob_20 프록시에선 패킹으로 도달 불가. 친구의 80k는 (a)진짜 P3가 프록시보다
유리하거나 (b)근본적으로 다른 패커. 히든이라 직접 검증 불가.
**성과 요약: v54로 108.8k→94k(로컬 @60), 그레이더 예상 ~90k = 친구 100k를 이미 상회.**

---
## (A) exact 크레인-MIP 배치 시도 결과 (prob_20)

**핵심 아이디어(래스터화 벽 우회):** 크레인 하강제약은 pairwise 분해됨(A의 하강이 present
블록들 상위레이어 *합집합*과 안 겹침 = 각각과 안 겹침 = OR of pairwise). 그래서 후보배치
(column) 쌍의 충돌을 **엔진으로 exact 계산**해 set-packing MIP에 넣으면 셀 래스터화 오차 없음.

**규모 벽:** 전체 MIP는 폭발 — bay1 하나에 step1이면 72,722 columns, 충돌 수백만(2D패킹
NP-hard가 발현). coarse/bbox 근사는 greedy보다 약함(bbox는 실루엣보다 커서 false conflict).

**해결 = LNS-윈도우(시간축 희소성 활용):** 동시존재 블록이 ~6개뿐이므로 greedy해에서
미배치 블록마다 시간이웃 ~8개만 풀어 작은 exact 크레인-MIP로 재패킹. Gurobi(WLS).
결과 (best-of-order greedy 시작 + multi-pass):
| bay | greedy(best) | exact-MIP-LNS | area-bound |
|---|---|---|---|
| bay1 | 44 | 44 (+0) | 52 |
| bay2 | 59 | **60 (+1, 검증)** | 62 |
| bay4 | 52 | 52 (+0) | 57 |
fine resolution(step1,cap60,free12)로도 bay2=60이 최대.

**판정:** exact MIP가 실제로 greedy를 이김(bay2 +1) → 개념·구현 성공, 래스터화 벽 극복.
그러나 진짜 기하+크레인 천장 = greedy+2 수준. **area-bound(+16)는 신기루**(느슨한 완화).
obj 환산 +2~3블록 → ~88-90k. **80k는 prob_20에서 패킹으로 도달 불가 (exact하게 증명).**
남은 이득: exact-LNS 통합 시 94k→~88-90k(~5%). 80k엔 진짜 P3 구조가 프록시와 달라야 함.
스크립트: scratchpad/fr2/lns_crane.py (Gurobi pairwise-conflict LNS, 재사용 가능).

---
## v55 — exact 크레인-MIP Z3 재배치 후처리 (통합 완료, -8%)

**(A) 시도의 실전 통합.** 검증된 exact 크레인-MIP LNS를 실제 파이프라인에 넣음.
`_z3_relocate(prob_info, assign, bay_unit, deadline)`: 저밀도 해에서 선호위반 블록(Z3>0)을
더 선호하는 bay로 옮김 — 타깃 bay의 시간이웃 ~8개를 풀고 그 작은 집합을 후보열 set-packing
CP-SAT로 exact 재패킹. 크레인 충돌은 ogc_fast 엔진으로 pairwise 정확계산(래스터화 없음).
Gurobi 아님 = **CP-SAT(ortools)** 라 그레이더 안전. 이동은 cheap _objective 델타로 게이트
(이동은 Z1=0 유지·한 블록 bay만 바꿈 → 산술 obj 정확), 최종 check_feasibility 재검증.

**통합 방식:** worker 0(1.0-reserve 워커)에서만, tail 예산의 35%(최대 20s)를 예약해서
Benders tail 뒤에 실행. worker 2(0.65)·홀수(0.0)는 그대로 → best-of never-worse.
예약은 시간제한에 적응적(작은 TL→작은 예약).

**측정 @60s (로컬 4코어):**
| 인스턴스 | v54 | v55 | |
|---|---|---|---|
| prob_20 (P3 프록시) | ~94k | **86.5k** (87188/85870) | **-8%** |
| prob_9 (저밀도) | 55815 | **50885** | -9% |
| prob_3 | 48370 | 48370 | 동일(never-worse) |
| prob_6 | 49770 | 49770 | 동일 |
| prob_30 (고밀도) | 3046457 | 3046457 | byte-identical |

Z3-relocate가 prob_20에서 5~6블록을 선호bay로 이동(Z3 646→~580). obj-게이트라
구조적으로 never-worse(이동은 엄격 개선일 때만 유지). 고밀도는 `_low_density` 게이트 밖이라 불변.
스크립트: scratchpad/fr2/z3_lns.py(Gurobi 원형), z3_cpsat.py/z3_fast.py(CP-SAT+cheap-obj).

**v55 견고화 (예산·never-worse 수정):** 초기 통합은 worker0에 20s 예약 → tail@40s가
가끔 수렴실패(obj 100k) → best-of가 worker2(0.65)로 못 떨어져 94k 회귀. 수정:
(1) worker2를 0.65→**1.0 full-tail**(무예약)로 = v54 winning basin 재현 → best-of 구조적 never-worse.
(2) relocate 파라미터 FREE=6/COLCAP=20으로 튜닝: 86.25k를 ~9s에(기존 8/24는 ~17s).
(3) 예약을 min(14, 0.25·remaining)로 축소 → worker0 tail이 수렴할 시간 확보.
(4) try_insert에 deadline-4.0 하드가드 + CP-SAT cap 축소 → 단일 윈도우 오버런 방지.
검증: worker0 단독 85160, 파이프라인 prob_20 @60 = 86.0~87.0k(안정), prob_9 v55≤v54(never-worse),
prob_30 byte-identical. **wall-time v54와 동일**(TL20/30/60 전부 +0.06~0.4s 프레임워크 오버헤드,
relocate는 deadline 하드바운드) → TLE 위험 없음. 그레이더 ~2배 빠름 → tail 더 확실히 수렴.

---
## 가설1 (Temporal Corridor Preservation) 연구 — tcp 모드, 밤샘 검증 결과

**메커니즘 규명:** coreperi("장기체류 대형→외곽")의 진짜 원리 = **시간축 파편화**. 장기체류 블록을
중앙에 놓으면 체류시간 내내 자유공간을 쪼갬. 이를 단일 원칙 점수로: `pt[b]·(A−LER)` (LER=최대
빈사각형=크레인 통로). 죽은 skyline이 진 이유도 규명 = 시간맹(활성 rect만 세야 + pt 가중).

**construction-level 검증 (step=2):**
| inst | ratio | bigleft | coreperi | flatbl | tcpL4 | tcpL6 |
|---|---|---|---|---|---|---|
| p9 | 0.33 | 1.06M | 1.13M | 1.06M | 0.94M | **0.90M(−15%)** |
| p24(P5) | 0.60 | 1.10M | 1.41M | 1.32M | 1.26M | **1.07M(−3.5%)** |
| p29 | 0.55 | 2.09M | 1.98M | 2.34M | **1.78M(−10%)** | 2.11M |
| p30(P4) | 0.90 | 4.06M | **4.06M** | 4.76M | 4.29M | 4.34M |
| p35 | 0.83 | INFEAS | **2.22M** | INFEAS | 2.90M | 2.34M |
| p38(sat) | 1.57 | 37.8M | **37.5M** | 38.2M | 38.2M | 40.0M |
→ tcp는 **저-중밀도 승자 + 크레인 feasibility 보험(p35)**, 고밀도(P4/P6)엔 못 이김.

**full-pipeline A/B (tcp를 _tails best-of에 추가, 60s):**
| inst | base | +tcpL6 |
|---|---|---|
| p24 | 578452 | 608197 (**−5% 악화**) |
| p30 | 3046457 | 3046457 (동일) |
| p35 | 1534895 | 1521340 (−0.9%) |
| p38 | 34512341 | 34512341 (동일) |

**결정적 통찰(나침반):** construction 품질은 **고밀도(Z1이 construction에 lock)에서만 최종점수에
영향**. 저-중밀도는 Z1≈0이라 ALNS가 seed를 완전 재작업→washout. tcp는 **정확히 반대**(저-중밀도
construction만 개선, 고밀도는 못함) + tail 추가가 예산절도 → 파이프라인 순이득 없음(p24 −5%).
**P4/P6 목표는 tcp로 불가**(construction·파이프라인 양쪽 확인).

**재사용 자산:** `_occ_grid`/`_ler_of`/`_lfr` 리팩터(byte-identical), tcp 모드(pt·(A−LER),
TCPL 양자화, LER 메모이즈 2-3배 가속), 전부 env-gated(TCPTAIL/TCPL default off) → **배포 v55 불변**.
다음 레버: 개선이 파이프라인에 남으려면 **고밀도 construction의 Z1을 직접** 겨냥해야 함.

---
## 통일 배치 스코어러 (unified) — mode-zoo를 하나로 뭉치기 (핵심 성과)

**동기(user):** 해 개선이 아니라 *따로 노는 조각(mode-zoo + ratio 게이트)을 하나의 일반화된
메커니즘으로 뭉치기*. 계산량↓, 과적합 없이, 일관되게. 해는 헤쳐도 됨.

**웹 리서치:** selection hyper-heuristics(Ross et al., bin-packing 일반화 입증), adaptive
operator selection(MAB), Squeaky Wheel Optimization(construct-analyze-prioritize).

**설계:** 개별 모드(bigleft=left, tcp=corridor, prefaware=pref, flatbl=flat)를 **하나의
가중 점수**로 뭉침: `score = wF·flat + wL·left + wB·bottom + wC·corridor + wP·pref` (정규화,
최소화). 각 모드 = 이 공간의 corner. corridor는 tcp의 LER(메모이즈). env 가중치, 게이트 0.

**construction 검증 (corr = F1 L1 B0.5 C2 P0.5, vs best-of{bigleft,coreperi}):**
p22 −11%, p24 +0.4%, p26 −0.1%, p28 −11%, p30 +4.6%, p31 −3.1%, p33 +9.1%, p37 −10%, p38 +0.5%.
→ **하나의 가중치가 9개 중 5개서 best-mode보다 좋고 2개 tie** — 게이트 없이 일관 generalize.
corridor 항(크레인)이 일반화의 핵심(진단된 crane-bound tardiness를 게이트 없이 흡수).

**full-pipeline A/B (unified가 mode-zoo 대체, bigleft=feasibility fallback, 60s):**
p28 −9.9%, p37 −1.5%, p22/p31/p38 동일, **p30/P4 +6.3%(악화)**.
p30 악화 이유: unified가 coreperi(p30 유일 승자)를 대체했는데 corr 가중치가 p30을 못 잡음.
(construction 스윕: pref-heavy 가중치는 p30 −16.9%였음 → 단일 가중치로 전부 최고는 불가.)

**결론(메커니즘 성공):** 따로 놀던 mode-zoo를 **게이트 없는 단일 가중 함수**로 대체 가능.
대부분 tie-or-win, p30만 +6.3%. 완전 일관성엔 **2개 가중치(corr+pref) best-of**면 충분
(mode-zoo 5개+ratio게이트 → 가중치 2개, 여전히 게이트-free·저비용). = AOS over WEIGHTS.
배포 v55 불변(unified/tcp/UNIFIED/UWx 전부 env-gated off). 스냅샷 갱신.
