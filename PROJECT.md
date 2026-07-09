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
