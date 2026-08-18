# [정정] bigleft × CP-SAT 순서 — 실제 엔진(C++ NFP) 검증 결과

## 요약 (이전 비트마스크 실험을 뒤집음)
`prototype/results/bigleft_cpsat_hybrid.md`는 **보수적 비트마스크 재현엔진**에서
"cpsat 순서가 rank를 26~45% 이긴다"고 했으나, **사용자 실제 엔진(submit_v34,
C++ ogc_fast NFP + numba, python3.12)에서 그대로 재현하니 정반대**였다.
→ 이전 결과는 엔진이 헐거워(크레인 여유 과다예약) 생긴 착시였다.

## 방법 (전부 사용자 실제 코드)
- 배치: `_smallright_construct(prob, DL, small_thresh=0.60, step=1, mode="bigleft")`
  — 큰 블록(area_rank<0.60) `sc=(h, wx, wy, j)` flattest→left→bottom,
    작은 블록(area_rank>=0.60) free-span gap-fill. **이게 gate 0.60 bigleft 경로.**
- 순서만 교체: 기본 `key=(rd+ra, due)`(=rank) vs `order="cpsat"`
  (`_cpsat_schedule(eff=0.63)` entry 시각으로 `key=(entry, due)`).
- 평가: 공식 `utils.check_feasibility` (Z1=obj1). 전부 feasible.
- 실행: python3.12 (cpython-312 .so 로드), DL=150~320s.

## 결과 — 고밀도 5개, 순서만 다름

| 인스턴스 | rank Z1 | cpsat Z1 | rank obj | cpsat obj | Z1 판정 |
|---|---|---|---|---|---|
| prob_27 | **1564** | 1788 | **23.40M** | 26.38M | rank +14% 우세 |
| prob_37 | **487**  | 659  | **6.74M**  | 7.71M  | rank +35% 우세 |
| prob_38 | **2359** | 2685 | **34.51M** | 38.50M | rank +14% 우세 |
| prob_39 | **490**  | 653  | **7.98M**  | 10.22M | rank +33% 우세 |
| prob_40 | **2416** | 2629 | **1.77M**  | 1.91M  | rank +9% 우세  |

**5/5 전부 rank가 Z1·총objective 모두 우세. cpsat 순서는 Z1을 9~35% 악화.**
- prob_38 rank Z1=2359 = 사용자 실측/코드주석과 정확히 일치 → 올바른 게이트 확인.
- 부수효과: cpsat는 CP-SAT가 베이부하를 균형화해 Z2를 종종 크게 줄이나(예: 38번
  1097→505), Z1 지배라 총obj는 그래도 나빠짐.

## 결론 / 권고
- **order="cpsat"를 배치 순서로 쓰지 말 것.** 고밀도 Z1-지배 인스턴스에서 rank보다
  일관되게 나쁨(실제 엔진 5/5). 이전 문서의 낙관 결론은 본 문서로 정정.
- 원인: CP-SAT는 유체 area-relaxed 모델을 최적화(균형/지각)해 순서를 짜지만, 그리디
  bigleft 배치는 그 순서대로 촘촘히 seat하지 못함. rank("급+큰 먼저")가 큰 블록을
  앞세워 연속공간을 선점 → bigleft 배치와 궁합이 맞아 지각↓.
- CP-SAT를 살리려면 "순서"가 아니라 다른 축을 검토: (a) bay 배정 힌트만, (b) ALNS
  repair oracle(고정 bay 부분문제를 CP로 정확해결), (c) eff 재튜닝. 순서 교체는 폐기.

## 재현
`sv34/run_bigleft_order.py <prob.json> <DL> rank,cpsat` (python3.12).
패치: `_smallright_construct`에 `order=` 인자 1개 추가(기본 rank=바이트동일),
`order=="cpsat"`일 때 `_cpsat_schedule` entry로 key만 교체.
