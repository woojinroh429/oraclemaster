# CP-SAT 순서를 배치와 하이브리드 — realized Z1 검증 (prob_38)

질문: 사용자 algo가 EDD/rank 순서를 배치에 먹이듯, CP-SAT 순서도 같은 배치엔진에
먹이면 지연이 낮아지나? → 같은 placer(bottom-left, 크레인 보수적) 고정, 순서만 교체.

## 결과 (realized Z1, 낮을수록 좋음, 전부 검증 위반 0 = feasible)

| dispatch 순서 | realized Z1 | vs EDD |
|---------------|------------:|:------:|
| EDD           | 6,196 | — |
| rank          | 7,991 | +29% |
| **CPSAT**     | **4,888** | **−21%** |
| CPSAT+bay     | 4,919 | −21% |

CP-SAT 순서 = area 완화(eff=0.63) 스케줄의 entry-time 오름차순. CP-SAT 60s.

## 결론
- **CP-SAT 순서가 realized Z1에서 EDD −21%, rank −39%.** area뿐 아니라 실제 2D 배치에서도 우위.
- **order-only(4888) ≤ CPSAT+bay(4919)** → 베이 강제보다 순서가 핵심. 통합은 순서만으로 충분.
- placer가 crude(bottom-left)라 절대값은 사용자 bigleft(2359)보다 나쁘나, 순서 효과는
  placer 고정 하 순수 비교라 유효. 사용자 bigleft에 얹으면 방향(개선)은 유지될 것으로 기대.

## 통합 (cpsat_order_patch.md)
`_hybrid_construct`에 `order="cpsat"` 추가(=`_cpsat_schedule`의 sched_entry를 dispatch key로).
CP-SAT를 프리스텝(풀 선점) 대신 **워커 하나**로 넣어 best-of로 포착 → v26 선점 문제 회피.
