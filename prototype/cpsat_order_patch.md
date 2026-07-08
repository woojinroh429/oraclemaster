# `order="cpsat"` drop-in 패치 — CP-SAT 스케줄을 배치와 하이브리드

목적: 지금 `_hybrid_construct(order="edd"/"rank")`가 스케줄 순서를 event-driven bigleft
배치에 먹이는 것처럼, **CP-SAT의 (더 낮은) 스케줄 순서를 같은 배치엔진에 먹인다.**
측정 근거: area 스케줄에서 CP-SAT가 EDD/rank보다 7/7 낮음(prob_38 1645 vs 2958).
`_cpsat_schedule`은 이미 코드에 존재 → 재사용.

## 패치 1 — `_hybrid_construct` 에 `order="cpsat"` 추가

`_hybrid_construct` 상단, order→`_key` 분기 (else 직전)에 삽입:

```python
    elif order == "cpsat":
        # CP-SAT area-relaxed schedule -> globally-optimised dispatch ORDER, fed
        # into the SAME event-driven bigleft placement (hybrid, exactly like edd/
        # rank).  Measured lower area-tardiness than edd/rank on all high-ratio
        # instances (prob_27/37/38/39/40).  eff=0.63 reserves crane corridors so
        # the order reflects a 2D-realisable schedule.  Any failure -> EDD.
        try:
            _car, _cbc, _csc = _footprint_areas(prob_info)
            _cs = _cpsat_schedule(prob_info, _car, _cbc, 0.63,
                                  max(4.0, deadline_s * 0.45), 4)
        except Exception:
            _cs = None
        if _cs is not None:
            _cs_tard, _cs_bay, _cs_entry = _cs
            _key = lambda b: (_cs_entry[b], due[b])   # dispatch by CP-SAT entry
            # (선택) 강한 버전: 배치도 CP-SAT 베이로 제약하려면 _big_bay_list 대신
            #        아래처럼 블록별 베이를 place 단계에서 _cs_bay[b] 우선으로.
        else:
            _key = lambda b: (due[b], due[b] - rel[b])   # fallback EDD
```

- CP-SAT는 event-loop 시작 전 **1회만** 실행(예산의 ~45%). 나머지로 배치 진행.
- `_key`만 바꾸면 나머지 event-driven bigleft 로직은 그대로 → 리스크 최소.

## 패치 2 — `_smallright_construct` 도 동일 (선택)

`_smallright_construct`의 `key=lambda b:(rd[b]+ra[b], due[b])` 를, cpsat 모드 인자
받아 `cen=_cpsat_schedule(...)[2]; key=lambda b:(cen[b], due[b])` 로 교체하는 오버로드 추가.
(bigleft 배치 정책은 유지, 순서만 CP-SAT로.)

## 패치 3 — 워커 라우팅에 cpsat 워커 추가

`algorithm()`의 워커 배정에서, 한 워커(예: 고혼잡 `_hi_ratio`일 때 n-3)를
`_hybrid_construct(order="cpsat")` 로 돌리고 best-of에 포함:

```python
    def _cpsat_worker(i):
        return (HAVE_ORTOOLS and _hi_ratio and n_workers >= 4 and i == n_workers - 3)
```

→ **핵심**: CP-SAT를 "풀 선점 프리스텝"이 아니라 **워커 하나로** 넣어, best-of가 그
이득(prob_28/36/38급)을 포착하되 다른 워커(EDD-hybrid)는 그대로 → P6 손실 없음.
(이게 v26에서 프리스텝을 껐던 이유 = 선점. 워커화하면 선점 문제 사라짐.)

## 주의 (정직)
- CP-SAT는 event-loop 시작 전 1회 → 그 시간만큼 배치 예산 감소. 고혼잡 큰 인스턴스에선
  CP-SAT가 순서를 개선해 상쇄될 것으로 기대(area 측정 근거). 저혼잡/소형엔 안 켜는 게 안전
  (`_hi_ratio` 게이트).
- 1코어 워커의 CP-SAT는 4코어보다 약함 → `deadline_s*0.45` 예산에서 나오는 순서가
  full-optimal은 아니나, area 측정상 그래도 EDD/rank보다 나음.
- 최종 실현 이득은 서버(엔진 replay)에서 확정 필요.
