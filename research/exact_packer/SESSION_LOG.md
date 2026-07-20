# 연구 세션 전체 로그 — 영구 기록 (competitor-gap → exact packer)

이 세션에서 무엇을, 왜, 어떤 순서로 알아냈는지의 완전한 서사. 다음 세션이 맥락을
잃지 않도록. (요약: v71 제출됨 = 현 최선; 그 뒤 며칠짜리 exact-packer 연구 1일차 완주.)

## 0. 출발점
- 대회: 조선소 블록 패킹/스케줄링. 목적 = w1*Z1(지각)+w2*Z2(부하불균형)+w3*Z3(선호).
- 히든 채점 P1~P6. 우리 v71: P1 11280, P2 31368, P3 102625, P4 3863913, P5 10417872, P6 28496957.
- 크레인 강하 제약(j>=k)이 핵심: 위에서 내리는 블록 레이어 k는 하강 중 기존 블록 레이어 j>=k와 안 겹쳐야.

## 1. v71 (제출됨, 현 최선)
- 변경: ortools cp_model을 워커별 lazy import -> 모듈 top-level eager import.
  fork Pool에서 4워커가 각자 예산 안에서 native lib 로딩하던 걸 제거 (0.4s x4 -> 0, 느린 그레이더선 더).
- 검증: fork-safe, 해 동일, 역대 최저 P3(106395->102625). 무회귀.
- 기각된 것들: v70(seed reseed, 퇴행), v72(LB필터, 무효), v73(STFRAC, 회귀), v74(row-gather decode 11%↑지만 obj 불변), v75(z3 aggr, 노이즈).

## 2. 성분 지도 (40개 훈련 인스턴스)
- 저밀도 27개: Z1=0, Z3 지배(65~99%). 고밀도 13개: Z1 지배(51~93%).
- 레짐은 크기(n,m) 아니라 시간혼잡도가 결정 -> n/m 게이팅 불가.

## 3. "물리 바닥" 오판 -> 경쟁자 증거로 반전 (핵심 전환점)
- floor probe: 우리 파이프라인 prob_20 = 89271에 수렴(120s=300s). "물리 바닥"이라 결론.
- BUT 사용자: 친구 P4=3.1M, 누군가 P3=81000. 우리 102625/3.86M보다 ~20% 낮음.
  => 89271은 물리바닥 아니라 **우리 지역최적 함정**. 20% 헤드룸 실재.

## 4. 20% 갭의 정체 = 패킹 밀도 (증명)
- packgap: 베이들 peak 74~85% area인데 스필 발생 (bay1: 62선호, 41만 배정).
- bay1 258% 과포화(면적) -> 스필 일부는 강제. 하지만:
- strongpack: 다중순서 greedy가 bay1에 44개 (st_best 41). 패킹 beatable.
- **gpack2/6 (Gurobi exact set-packing): 혼잡 clique(17블록)에 greedy=7 vs Gurobi=10 (+43%).**
  => 우리 greedy가 혼잡구역 심각히 under-pack. exact가 훨씬 더 넣음.
  => 더 넣음 -> 스필↓ -> Z3↓(P3) & Z1↓(P4). 한 레버가 양 레짐 20% 설명.

## 5. 수리모형 (형식화 + 검증)
- Master(gmaster): Gurobi 배정 MIP min w2Z2+w3Z3, area-relaxed (CP-SAT와 일치 검증).
  area 용량은 크레인 feasibility 표현 못함(oracle: cf=0.70도 infeasible) -> LBBD-over-area 죽은길(lbbd).
- Subproblem(심장): per-bay 크레인 패킹 = SET-PACKING over 배치컬럼 c=(block,x,y,orient,entry).
  cover sum<=1, 충돌쌍 y+y'<=1, max 개수/선호.
- 혼잡윈도우 = interval graph의 PEAK CLIQUE (congestion): peak 순간 공존 블록. 5~18개(작음).
- 방향은 블록별 O_i (2/4/6/8, 대칭이면 적음). 레이어수도 블록별 K_i.
- 진입시각: 이벤트기반 {release}∪{exit들}. 저밀도 Z1=0이면 t=release 고정 (최적성 손실 없음, semi-active).

## 6. 충돌 규칙 (VALIDATED, C++ 포팅 기준)
- 두 배치 충돌 iff 시간공존 AND: 안착(A_k vs B_k) + 나중진입/먼저퇴장자가 상대 상단레이어(j>k) sweep.
- 겹침 = 레이어 다각형 area>0. **좌표는 layers_at_pos()(world) — resolved_layers()(원점) 아님!! (반나절 버그)**
- fastconf.conflict가 grader_conflict(원시함수)와 prob_20/17 0-mismatch. numba _g_classify_pair 0.48us.

## 7. 속도 벽 (여러 시도 -> 진짜 병목 규명)
- fine grid(step<=3): 컬럼 5k~10k -> 21M쌍 -> conf/solve 불가. 병목 = 컬럼수 (충돌속도 아님).
- FFT 충돌마스크(fftmask): 정확(1.1% false-neg, cut로 처리)하나 컬럼수 벽 못 넘음.
- extreme-point 컬럼(ep_verify): x접촉xy접촉 곱 ~37000. 8방향xn블록 곱이 안 줄어. 죽은길.
- NFP-MIP(compact): 이론상 맞지만 불규칙 nesting NP-hard, ~17조각 경계.
- coarse-to-fine(ctf): step6=10 -> fine재배치=10. 이 clique는 10이 천장(258%과포화). fine 불필요.
- step sweep: step8=9, **step6=10(최적)**, step5=9, step4=7. 촘촘할수록 고정시간엔 오히려 나쁨(모델 커서 timeout).

## 8. 확정 결론 (다음 세션)
- **step6 coarse set-packing이 최적(10) 캡처, 풀리는 규모.** 해상도 더 안 올려도 됨.
- 병목 = solve/conf 속도 (파이썬 clique당 ~65s). => **C++ 하나면 됨** (NEXT_SESSION.md 스코프 참조).
- C++로 step6을 ~1s -> 모든 binding clique에 LNS 적용 -> 전체 A/B -> 이기면 v72.
- 현 제출 최선 = v71. 패커 검증 전까지 유지.

## 파일 (research/exact_packer/)
gmaster oracle lbbd congestion conflictgen fastconf raster fftmask gpack2..6 ep_verify ctf
+ NEXT_SESSION.md (C++ 착수) + README.md + 이 SESSION_LOG.md
