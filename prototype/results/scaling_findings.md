# 전체 100블록(prob_1) 스케일업 실측 + Numba 가속 검토

목표 참조값: prob_1 전체 obj ≈ **1499** (Z1=0, Z2↔Z3 균형).

## 1. 100블록 현재 상태 = 아직 INFEASIBLE

`solve_colgen prob_1 100 5 4 4 1 15` 실측 (results/cg100_summary.log):
```
build 15.1s, 43,490 placements, cells 122,599
round 0: +99 cols
round 1: LP status 4 (ABNORMAL, 수치불안정) → pricing 조기 중단
[int] INFEASIBLE (1.9s)
```
원인:
- **LP 수치불안정(status 4)**: 셀 제약 12만개의 퇴화(degenerate) LP → 쌍대 신뢰 불가 → 열생성 정지.
- **열 풀 부족**: 블록당 ~9열(시드)만으론 100블록 무충돌 배치 불가 → 정수 INFEASIBLE.

즉 1499(품질)에 앞서 **feasibility + 수치안정**이 먼저 해결돼야 함.

## 2. Numba 가속 — pricing 핫루프 기준 측정

`bench_numba.py` (셀 4000, 후보 20000, 후보당 60셀 점유, Σμ 계산):
| 구현 | 시간 | 
|------|------|
| 순수 Python (dict 스캔) | 146.2 ms |
| Numba njit (uint64 워드) | 16.0 ms |
| **speedup** | **9.1x** (결과 일치 검증) |

- naive 커널(비트인덱스 log2 추출)로도 9x. De Bruijn/trailing-zero, 팁1 다중워드 팩킹 적용 시 20~50x 기대.
- **Numba가 해결하는 것**: pricing 처리량(라운드 수·그리드 해상도·블록당 top-k 열).
- **Numba가 해결 못 하는 것**: LP 수치불안정(GLOP는 이미 C++), 정수 INFEASIBLE(모델링),
  1499 도달(목적 유도). → Numba는 enabler이지 만능이 아님.

## 3. 1499로 가는 경로 (Numba는 ③의 도구)

1. **feasibility 시드**: baseline greedy(EDD)로 무충돌 배치 1개를 초기 열로 → 정수 INFEASIBLE 방지.
2. **Z2를 마스터 LP 목적에 선형화 삽입**: 지금은 정수단계에서만 Z2를 봐서 CG가 균형 열을
   안 만듦 → LP가 부하균형 방향으로 열을 생성하도록.
3. **Numba pricing + 블록당 top-k 열**: 라운드당 다수 열을 빠르게 → 풀 다양성↑ (9~50x 값어치).
4. **LP 안정화**: 퇴화 완화(perturbation/제약 집계) 또는 대회 제공 Gurobi 사용.

네 가지가 함께 들어가야 100블록 feasible → 1499 근처. Numba 단독으로는 불충분.
