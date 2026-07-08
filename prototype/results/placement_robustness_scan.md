# 40개 인스턴스 placement 실측 스캔 — NFP fallback 효용 + degenerate 견고성

## 방법 (실제 엔진, python3.12)
각 인스턴스를 bigleft/rank 구성, NFP fallback OFF(v34기본)/ON 비교(`run_scan.py`).
미배치 블록수, Z1, 공식 check_feasibility. 원인진단 `run_infeas.py`.

## 결과 1: 미배치(placement 실패) = 40/40 전부 0
모든 인스턴스가 OFF/ON 둘 다 100% 배치. **견고 NFP가 '배치 완성'엔 불필요.**

## 결과 2: NFP fallback 효용 = 거의 무의미
OFF vs ON 거의 전부 동일. 예외 딱 2개:
- prob_39: 516 -> 486 (NFP가 Z1 -30 개선)
- prob_31: 287 -> 296 (NFP가 오히려 +9 악화)
=> 순효과 ~0. **견고 NFP를 Z1 목적으로 도입할 가치 없음(v34가 NFP 끈 판단 옳음).**

## 결과 3 (실측 가치 발견): degenerate zero-area 접촉으로 인한 구성 infeasible
standalone 검증 결과 bigleft 구성이 **infeasible**한 인스턴스: prob_15,16,19,34 (~4/40=10%).
전부 위반 **area=0.000** (정확히 맞닿은 경계):
- prob_15 stage2: block37 진입이 block102와 collision area=0.000
- prob_16 stage2: block77 진입이 block75와 sweep+collision area=0.000
- prob_19 stage2: block21/299 진입 collision/sweep area=0.000 (5건)
- prob_34 stage3: block160 이탈이 block176과 sweep area=0.000
**근본원인: 빠른 C++ 엔진 placement_feasible은 exact-touching(area=0)을 통과시키나
공식 checker(utils/shapely)는 위반으로 잡음 = 엔진↔검증기 degenerate 불일치.**

### 제출 위험? 아님 (내부검증이 걸러냄)
algorithm()은 최종 출력을 공식 check_feasibility로 검증하고 통과 해만 반환(line 2670,
주석 line 12). 따라서 degenerate 구성은 best-of/ALNS/검증이 폐기 -> 제출엔 안 나감.
단, 그 ~4개 인스턴스에서 bigleft 전략이 낭비되고 대체 전략/repair에 의존.

### 연결: 이게 robust-NFP/sparrow 논문이 실제로 돕는 지점
sparrow는 "아이템을 항상 minuscule epsilon 이상 분리"(exact-touch 금지)로 이 문제를 원천
차단. robust-NFP(1903.11139)도 degenerate 처리가 핵심. 즉 이 논문들의 가치는 **Z1 감소가
아니라 견고성**(degenerate 접촉 제거로 엔진=검증기 일치).

### 가성비 좋은 fix(제안, 미적용)
placement_feasible에 미세 분리마진(epsilon 또는 정수 1) 요구 -> 엔진feasible⇒공식feasible
보장. 단 고밀도에서 밀도 소폭 감소 가능(Z1 트레이드오프) => 저밀도에만 적용 권장.
또는 최종검증 실패 블록만 1-unit 넛지 micro-repair.

## 부록: 전 인스턴스 Z1 지형 (bigleft/rank, 참고)
Z1=0(저밀도, Z2/Z3 게임): prob_1-14,17,18,20,29 등 다수.
Z1>0(지각바운드): 21(52),23(193),25(351),26(605),27(1564),30(209),31(287),32(364),
33(949),35(61),36(71),37(484),38(2359),39(486),40(2465). => 고밀도만 지각 지배.
