# 대안 패커/스케줄러 심층 리서치 종합 (100 에이전트, 검증완료)

## 질문
crane-제약 조선소 블록 spatial-scheduling에서, 로컬 패킹/윈도우 스케줄이 이미 near-optimal
(exact CP-SAT OPT 증명)임이 확인된 tuned heuristic을 **전역적으로 ~20% 이길** 방법이 있는가?

## 핵심 결론 (리서치 ↔ 우리 실증 일치)
**갭은 "배치 순서(allocation-order / sequencing) 레이어"에 있다 — 패커가 아니다.**
- 조선소 OR은 bottom-left-fill 위에 **순서·방향을 메타휴리스틱으로** 최적화 (패커는 고정).
- 우리 실증과 정확히 일치: 로컬 밀도/윈도우는 near-optimal, 남은 여지는 전역 구조.

## 검증된 후보 (confidence high)
1. **순서 레이어 전역 메타휴리스틱** — VLNS ruin-and-recreate(큰 파괴), memetic/GA(제약인지 연산자),
   DRL-improvement(완성해 개선, ALNS 호환). 패커층 DRL-constructor는 우리가 이미 배제한 near-optimal층.
   → **v71은 이미 BRKGA over orders 사용.** 더 강한 순서탐색(VLNS)이 유일한 열린 graft.
2. **LBBD (MIP master + CP subproblem, 진짜 2D no-overlap)** — Nascimento/Silva/Antunes/Moniz 2024,
   EJOR 317(1):92-110. 2D 불규칙 nesting + release/due/tardiness를 **최적으로 푼 최초 문헌**.
   우리 area-Benders와 차이: 서브문제가 **면적 아닌 진짜 no-overlap** 강제 (하한이 crane-realisable).
   → 구조적으로 옳은 전역결합. 단 n=100-2700/30-60s엔 무거움 (matheuristic 가속 필요).
3. **column-generation for min-max Z2** — 이론상 맞지만 **160 jobs/10분** (van den Akker 2010) → 규모 안됨.

## 핵심 경고 (confidence high)
**CP-SAT-near-optimal 엔진 대비 검증된 ~20% 이득 사례는 문헌에 없다.**
→ 경쟁자 20%는 (a) 히든 인스턴스 구조 차이, (b) 다른 baseline, (c) 규모/스케일 차이일 가능성.
   우리 훈련셋에선 v71이 near-optimal이 반복 확증됨.

## 우리 실증과의 종합 (이번 세션)
- **v71 수렴 headroom ~5%**: prob_20 30s≈93k vs 120s=88.5k. 30초 미수렴(compute-bound).
  → 유일하게 실행가능한 실측 레버. "최적 넘기"가 아니라 "아는 더 나은 해에 빨리 도달".
  단 병목이 CP-SAT solve + 3DTCS decode(이미 C++)라 cranepack 충돌가속이 직접 도움인지는 불확실.
- 리서치의 "순서 레이어" 결론 + 우리 "수렴 headroom" = **다음 세션 타깃 = 순서탐색 강화**
  (VLNS ruin-and-recreate가 BRKGA보다 30초 내 더 잘 수렴하는지 A/B).

## cranepack의 실제 쓸모 (재평가)
- 패커-밀도 레버로는 죽은 길 (증명됨).
- 그러나 **VLNS repair의 빠른 crane-feasibility 오라클** 또는 **LBBD 서브문제(진짜 no-overlap 체크)**로는
  여전히 유효 — 100배 빠른 충돌이 그 자리에서 반복호출 가속.

## 출처
- He/Hong/Kim, J. Scheduling 2024 (KSOE 2-phase 구성): link.springer.com/article/10.1007/s10951-024-00804-1
- 조선 블록 allocation(DE on sequence), PPC 2008: tandfonline.com/doi/abs/10.1080/09537280802474941
- Nascimento et al., EJOR 2024 (LBBD nesting+tardiness): (EJOR 317(1):92-110)
- van den Akker et al., J.Scheduling 2010 (min-max CG): DOI 10.1007/s10951-010-0191-z
- 전체 검증 로그: deep_research_raw.jsonl
