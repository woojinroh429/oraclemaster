# coreperi 전용 워커 (numba guard 교체) — 검증된 무회귀 개선 ★

## 변경 (submit_v34 -> v35)
numba guard 워커(W = n-1, -1 보험용)를 **coreperi 전용 하이브리드 워커**로 교체.
- coreperi = 장기체류 대형블록 외곽배치(core-periphery). 일부 P3/P4/P6에서 승, 포화 P6에선 패.
- **ADDITIVE** 워커 + best-of-final(min) => 이기는 곳만 취하고 나머진 무회귀.
- coreperi 실패 시 `_solve_once(use_cpp=False)` numba fallback => -1 보험 유지.
- 구현: `_coreperi_for(i)=(i==n_workers-1 and n_workers>=4 and 엔진있음)`, worker_entry에
  coreperi_flag 추가, hybrid 경로에서 primary=coreperi 강제. place_custom에 coreperi/
  bigright/bigtop 모드 추가. (패치: prototype/coreperi_worker.patch)

## 왜 "교체"가 아니라 "전용 워커"인가 (실측으로 배운 것)
- 구성-only 비교는 coreperi가 v34 이기는 듯 보였으나, full 파이프라인에선 대부분 흡수됨.
- coreperi를 기존 primary(bigleft) 자리에 **교체**하면 포화 P6(prob_38/40)에서 회귀
  (coreperi가 거기선 bigleft보다 나쁨).
- **전용 워커로 추가**하면 best-of가 min 유지 => 이기는 곳(prob_33)만 취함, 회귀 0.
- numba guard는 저가치(-1 보험)라 그 슬롯을 coreperi로 재활용 = 공짜 primary 슬롯.

## 검증: 깨끗한 A/B (같은 코드, coreperi 워커 on/off, TL=120s)
| 인스턴스 | ratio | base obj | +coreperi obj | 효과 |
|---|---|---|---|---|
| **prob_33** | 1.14 | 7,605,106 (Z1=958) | **6,494,780 (Z1=810)** | **+14.6% WIN** |
| prob_37 | 0.96 | 6,685,147 | 6,685,147 | tie |
| prob_32 | 0.86 | 4,781,024 | 4,781,024 | tie |
| prob_40 | 1.33 | 1,943,562 | 1,943,562 | tie |
| prob_38 | 1.57 | 34,512,341 | 34,512,341 | tie |
| prob_27 | 1.63 | 23,400,112 | 23,400,112 | tie |
| prob_1  | low  | 1,499 | 1,499 (feas) | tie(안전) |

=> **prob_33 +14.6%, 나머지 6/6 회귀 0.** 무회귀 배포 가능.

## 주의 (정직)
- prob_33 외 테스트셋에선 tie => 이득은 coreperi가 실제 이기는 특정 인스턴스에 국한.
  히든에 prob_33류(중~고밀도 미포화, coreperi 궁합)가 몇 개냐에 따라 총점 영향 결정.
- n_workers<4(서버 코어<4)면 게이트가 꺼져 numba guard 유지 => 그 환경선 무변화(안전).
- 서버가 실제 4워커라는 전제(사용자 확인). W3 슬롯을 coreperi로 재배정.

## 남은 작업 (사용자 요청)
- P1/P2 저밀도 Z2 최적화: 측정결과 저밀도 목적은 Z2(부하불균형) 지배(prob_1 w2*Z2=1099 vs
  w3*Z3=400). Z3는 이미 ~0. => Z2 부하균형 배정이 레버. 별도 조사 필요.
- 맞물림(pair-packing)/density-score 정렬: 미구현. 밀도가 3D레이어겹침에서 와서(2D union
  16~32%) 고밀도 2D pair-packing 헤드룸은 작을 것으로 추정. density-score 정렬은 값싸 테스트가치.

---

## 추가: degenerate zero-area 접촉 infeasibility 리페어 (구현+통합)
문제: C++ 엔진 placement_feasible이 exact-touch(area=0)를 통과시키나 공식 checker는 위반
처리 -> 구성이 infeasible(prob_15/16/19/34, 저/중밀도).

수정: `_repair_touch(prob_info, recs, budget)` 추가. 공식 checker가 지목한 위반 블록만
엔진으로 entry를 1+ 지연 재배치하고 **공식 checker로 재검증**해 non-touching 자리 확보.
`_attempt`에서 구성이 infeasible(stage 2/3/4)일 때만 호출(feasible엔 오버헤드 0).

검증(구성 리페어):
| 인스턴스 | 구성 | 리페어 후 | Z1 비용 |
|---|---|---|---|
| prob_15 | infeas stage2 | feasible(1회) | 0 |
| prob_16 | infeas stage2 | feasible(1회) | 1 |
| prob_19 | infeas stage2 | feasible(3회) | 2 |
| prob_34 | infeas stage3 | feasible(1회) | 84 |

full algorithm() 검증: prob_15/16/34 전부 feasible, prob_33 +14.6% 유지(무회귀).

정직한 영향: 최종 점수는 ~불변(그 인스턴스들은 다른 워커/polish가 이미 더 좋은 feasible
해를 냄, 예: prob_15 최종 obj 56165 << bigleft-repaired 1.30M). 가치는 **견고성 보험**:
히든에서 모든 구성이 degenerate에 걸리는 병적 케이스 방지 + bigleft를 모든 곳에서 유효 후보화.
