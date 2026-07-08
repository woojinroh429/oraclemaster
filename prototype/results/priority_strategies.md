# 배치/우선순위 전략 대량 실험 — 전부 rank 못 이김 (실제 엔진)

사용자 제안 전략들을 실제 submit_v34 엔진(bigleft gate0.60)에 얹어 검증. 순서=rank 대비.

## 핵심 구조 사실 2가지 (여러 전략이 여기서 무효화됨)
1. **over-subscribed**: peak 수요>용량, 대기블록 100% 삽입불가(bay_fill_verification). →
   의도적 지연/공간예약(빈 core, 시간버킷, JIT-pull)은 동시수용량을↓ = 대기↑ = Z1 악화.
2. **exit = entry + processing (즉시이탈)**: 구성이 ex=cur+pt로만 배치하고 check_feasibility가
   크레인 exit까지 통과 → overstay 없음. → 체류시간은 이미 최소(=processing), "exit-blocking
   도미노 지각"은 이 엔진에 존재하지 않음. 이를 노린 전략(버킷 동기화, JIT-pull)은 무효.

## 결과 요약 (Z1, rank=baseline)
| 전략 | prob_37 | prob_38 | prob_39 | prob_40 | 판정 |
|---|---|---|---|---|---|
| rank (due+area) | 487 | 2359 | 490 | 2416 | 기준 |
| core-periphery(장기체류→외곽) | **477** | 2445 | 611 | 2504 | 37만 이김 |
| sacrifice sac3(최악3 유배) | **470** | 2371 | 500 | 2575 | 37만 이김 |
| sacrifice sac5 | 541 | 2368 | 493 | 2450 | 전부 짐 |
| space-time density(회전율,작은것먼저) | — | 3036 | — | — | 대패(+29%) |
| ATC(면적가중) | 519~590 | 2497 | — | — | 짐 |

## 다변수 스코어링 (prob_38, "블록 전 변수로 스코어링")
due/area/proc/rel/**width/height**/workload/preference 정규화-랭크 가중합:
| 조합 | Z1 |
|---|---|
| **rank(due+area)** | **2359** |
| +width .5 | 2560 |
| +height .5 | 2435 |
| +proc(long) | 2471 |
| +proc(short) | 2520 |
| +width+height | 2436 |
| width-heavy | 2558 |
| all(전변수) | 2529 |
| all-geom-heavy | 2663 |
→ width/height/processing/workload/preference 어떤 것을 더해도 rank 악화. due+area 2개가 핵심.

## 결론
- 지각엔 **due(급함)+area(큼)** 2신호가 전부. 나머지 블록변수는 노이즈(우선순위 왜곡).
- over-subscribed + 즉시이탈 구조 때문에 지연/예약/동기화 계열 전략은 원리적으로 손해.
- core-periphery / sac3 은 prob_37 전용 best-of 변형으로만 가치(단독 룰이면 회귀).
- 남은 유일 레버는 여전히 배치밀도(정확 nesting)뿐이며 window-LNS가 국소 프록시로 0 확인.

## 추가된 코드 (실험용, _smallright_construct)
order: "stdens"/"stdens_u"(회전율), "sacN"(희생양), "atc"/"atcN"/"atcaN"(ATC),
mode:"coreperi", feat_w={특징:가중} (다변수). 재현: run_feat.py / run_mode.py / run_bigleft_order.py.
