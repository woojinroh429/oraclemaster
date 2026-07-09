# OGC 2026 — Colab 전략학습 (고밀도 지각 최소화)

두 가지 코드:
- **`es_real_engine.py` ★권장** — 실엔진(C++) 위 ES. fitness=실엔진 공식 objective라
  전이문제 없음, 해는 항상 공식 checker 통과. (강력 권장)
- `ogc_gpu_rl.py` — 근사 시뮬 위 ES (참고용). 시뮬-실엔진 불일치로 전이 안될 수 있음.

────────────────────────────────────────────────────────────────────────
## ★ es_real_engine.py — 실엔진 위 ES (권장)
────────────────────────────────────────────────────────────────────────
신경망 정책이 per-block priority를 내면 실엔진 `_smallright_construct`의 `ext_entry`로
주입 -> 그 순서로 bigleft 배치 -> 공식 `check_feasibility` objective = fitness.
OpenAI-ES가 신경망을 최적화. GPU=신경망 forward, 엔진구성=CPU 멀티프로세스.

### Colab 준비 (중요 — .so는 Python 3.12 전용)
```bash
# 1) Python 3.12 확보 (Colab 기본이 3.10/3.11이면 필요)
!sudo apt-get update -qq && sudo apt-get install -y python3.12 python3.12-venv
!python3.12 -m venv /content/v312
!/content/v312/bin/pip install -q ortools numba shapely numpy torch
# 2) 파일 업로드
#    ./engine/  <- submit_v35: myalgorithm.py, utils.py, ogc_*.so (3개)
#    ./instances/ <- 고밀도 인스턴스 JSON (n=100 권장: 빠름. 예 prob_25,27)
# 3) 실행
!/content/v312/bin/python es_real_engine.py
# 4) 학습후 best_policy.pt + best_theta.npy 저장. 정책 주입은 ext_entry로.
```
GPU는 신경망만 가속(엔진은 CPU). 그래도 전이문제 없는 "진짜 학습"이라 가치 큼.

### 속도 (참고)
- fitness 1회 = 엔진 1구성 ≈ n=100 ~9s, n=250 ~70s+. pop32 n=100 => 세대당 ~70s(/4코어).
- 300세대 ~6h. best_policy 10세대마다 저장 -> 세션끊겨도 재개. 고밀도만/소수 인스턴스 권장.
- 더 빠르게: STEP=2, n작은 고밀도, POP↓, 인스턴스 1~2개.

### 설정 (CFG)
ENGINE_DIR(=./engine), INSTANCE_DIR, DEADLINE(구성예산), STEP(1/2), POP/GENS/SIGMA/LR/HIDDEN.

### 학습 결과를 submit에 반영하려면
best_theta로 신경망 priority를 재계산 -> 그걸 `_smallright_construct(..., ext_entry=priority,
tiebreak="due")`로 주입하는 워커를 submit_v35에 추가(coreperi 워커처럼 dedicated + best-of).
반드시 A/B(공식 checker)로 rank 대비 무회귀 확인 후 채택.

────────────────────────────────────────────────────────────────────────
## ogc_gpu_rl.py — 근사시뮬판 (참고)
공식 크레인체크로 유효해는 내나 느림+그리디 품질저하. 근사탐색용. 자세한 한계는 코드 주석.

## 배경 (이미 밝혀진 것)
- rank(due+area)+bigleft가 고밀도 near-optimal (ES가 근사엔진에서 독립 재발견).
- 근사엔진 학습전략은 실엔진 전이 실패 -> 그래서 **실엔진판(es_real_engine.py)이 정답**.
- 채택된 실이득: coreperi 전용워커(중밀도 -14.6%, submit_v35 반영).
