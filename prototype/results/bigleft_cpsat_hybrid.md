# bigleft 배치정책 × CP-SAT 순서 하이브리드 — 고밀도 realized Z1

## 목적
사용자 알고리즘의 **실제 bigleft 배치정책**(crude bottom-left 아님)을 재현해서,
dispatch **순서**만 rank(현재) vs CP-SAT로 바꿔 realized Z1을 측정.
"edd/rank로 배치와 하이브리드하던 걸 CP-SAT와 똑같이 하이브리드"의 검증.

## 배치정책 재현 (`bigleft_hybrid.py :: place_bigleft`)
- 면적순위 `ra[i]` 계산 → `ra>=0.60` 이면 **작은 블록**, 아니면 **큰 블록**.
- 큰 블록 score `(오리엔테이션 높이 h, x, y, bay)` → **낮고 좌측·바닥**에 클러스터.
- 작은 블록 score `(-free_span, y, x, bay)` → 바닥밴드(0.6·H) 내 **연속 수평 여유 최대**
  위치로 gap-fill (동시상주 블록들의 x-구간 병합 후 최대 갭).
- feasibility: 비트마스크 엔진(크레인 보수적 shadow). **검증 위반 전부 0**.
- 순서: `rank = sort((rd+ra, due))` (현재) vs `CPSAT = sort((entry, due))`
  (CP-SAT area-relaxed, eff=0.63 크레인 코리도 예약, 120s).

## 결과 (SX=2, CP-SAT 120s, 개당 build 포함 2.5~8분)

| 인스턴스 | rank+bigleft | **CPSAT+bigleft** | 개선 |
|---|---|---|---|
| prob_27 | 3905 | **2610** | −33.2% |
| prob_37 | 2259 | **1233** | −45.4% |
| prob_38 | 7607 | **4347** | −42.9% |
| prob_39 | 2205 | **1414** | −35.9% |
| prob_40 | 6482 | **4781** | −26.2% |

**5/5 전부 CP-SAT 순서가 rank 순서를 26~45% 이김. 전부 검증 위반 0.**

## 정직한 한계 (절대값 해석)
- 재현판 절대 Z1(예: prob_38 rank=7607)은 사용자 실제 알고리즘(2359)보다 **훨씬 큼**.
  원인 = 이 실험 엔진이 **보수적 비트마스크 shadow**(크레인 여유를 실제 NFP보다 과하게 예약)
  + 단일패스 event 배치(ALNS 개선/멀티전략 best-of 없음). 즉 엔진 자체가 실제보다 약함.
- 따라서 **절대값 이식 금지**. 이식 가능한 결론은 **"같은 엔진 내 상대 개선"**:
  → 실제 bigleft 엔진에 dispatch 순서를 CP-SAT로 바꾸면 고밀도에서 큰 이득 기대.
- 실제 서버 엔진(정확 NFP)에서 최종 확정 필요.

## 적용 방법 (기존 코드 최소수정)
`prototype/results/cpsat_order_hybrid.md` + `cpsat_order_patch.md` 참조:
`_hybrid_construct`/`_smallright_construct`의 `_key`만 CP-SAT entry 기반으로 교체
(`_cpsat_schedule` 이미 존재, 재사용). 배치정책(bigleft)은 그대로, **순서만** 교체.
워커 1개로 넣어 best-of에 포함(선점 방지) → 저혼잡 손실 없음(`_hi_ratio` 게이트).
