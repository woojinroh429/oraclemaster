# OGC 2026 — Colab 전략탐색 (고밀도 지각 최소화) + 정직한 한계

OpenAI-ES(진화탐색) + 신경망 정책으로 dispatch/position 전략을 학습하는 연구 스캐폴드.

## ★ 정직한 상태 (반드시 읽을 것)
이 문제의 시뮬레이터는 두 방향 다 벽이 있다:
1. **빠른 근사 시뮬(비트마스크 shadow)**: 크레인 exit-sweep을 못 맞춰 **공식 checker에서
   무효 해**를 낸다(Stage3 sweep 위반 확인됨). => 학습해도 무효.
2. **정확한 시뮬(공식 utils check_entry/exit)**: 유효 해를 내지만 (a) shapely라 **느림**
   (n=100 롤아웃 ~14s), (b) 이 스캐폴드의 그리디가 **품질이 낮다**(정적순서+후보제한 ->
   Z1이 baseline보다 훨씬 큼).

=> **좋고+빠르고+정확한 시뮬 = 사실상 그들의 C++ 엔진 재구현**(=이 대회의 핵심 난제).
   그래서 Colab만으로 RL이 실제 이득을 내긴 어렵다. 아래 현실적 경로 참고.

## 현실적 경로 (권장)
- **A. 실엔진 위에서 ES (가장 효과적)**: submit_v35의 `_smallright_construct`(C++엔진, 빠름+
  정확)를 시뮬로 쓰고, dispatch/position 정책을 ES로 학습. 로컬(그들 환경)에서 실행.
  (레포 `prototype/rl_strategy.py`가 근사엔진판; 실엔진판으로 바꾸면 전이문제 사라짐.)
- **B. Colab은 근사탐색 전용**: 이 코드로 dispatch 우선순위를 rough 탐색 -> **반드시**
  실엔진/공식 checker로 재검증. (과거: 근사학습 전략이 실엔진 전이 실패 사례 있음.)

## 파일
- `ogc_gpu_rl.py`  ES 학습. rollout이 **공식 크레인체크 사용**(해는 유효, 느림).
  `CFG`로 POP/GENS/TOPK_POS 등 설정. GPU는 신경망 forward만 가속(롤아웃은 CPU).
- `eval_export.py` 학습정책 -> operations 해 저장 + **공식 check_feasibility 검증**.
- `utils.py`, `baseline_greedy.py`  공식 baseline에서 복사(필요).

## 사용법 (Colab)
```python
!pip install shapely numpy torch
# utils.py, baseline_greedy.py, instances/*.json (고밀도) 업로드
!python ogc_gpu_rl.py     # 학습(느림; best_policy.pt 주기저장)
!python eval_export.py    # 유효 해 저장 + 공식검증 Z1 출력
```

## 개선 여지 (이 스캐폴드의 그리디 품질을 올리려면)
- rollout을 **정적순서 -> 이벤트구동**(baseline_greedy처럼 릴리즈/이탈 시점 배치)로.
- `TOPK_POS` 제한 완화(속도-품질 tradeoff), 위치 정책을 더 풍부하게.
- 그래도 속도가 관건 -> 경로 A(실엔진) 권장.

## 이미 밝혀진 배경
- rank(due+area)+bigleft가 고밀도 near-optimal(ES가 근사엔진에서도 독립 재발견).
- 근사엔진 학습전략은 실엔진 전이 실패(rank가 여전히 최선). => 시뮬-실엔진 일치가 관건.
