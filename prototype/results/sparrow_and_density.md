# sparrow 논문 검토 + 배치밀도 한계 규명 (실제 엔진)

## 논문: arxiv 2509.13329 "sparrow" (Gardeyn, Vanden Berghe, Wauters, 2025)
- **2D 불규칙 strip packing(nesting) SOTA 오픈소스 휴리스틱.** jagua-rs CDE 기반(초당 수백만
  충돌질의). 2단계: exploration(80%, 겹침 허용 광역탐색) + compression(20%, 압축).
  핵심=순차 greedy 아닌 **연속 겹침최소화(separation)**로 전역 밀집 배치.
- Python 래퍼 spyrrow, 3D판 sparrow-3d 존재. 코드 github.com/JeroenGar/sparrow.

## 우리 문제 적합성 판정 — 측정으로 sparrow-2D 배제
`run_overlap.py`: rank 해에서 peak 순간 베이 내 블록 footprint 겹침 측정.
| 베이 | 블록 | sum/union | 2D union/bay | sum/bay |
|---|---|---|---|---|
| prob_38 bay0 | 17 | 2.29× | 32% | 74% |
| prob_38 bay1 | 34 | 3.08× | 23% | 69% |
| prob_38 bay2 | 34 | 3.80× | 16% | 62% |

→ 우리 밀도는 **cross-level(레이어) 겹침**에서 옴(footprint 2.3~3.8배 중첩). 2D 바닥은
  16~32%만 사용. **순수 2D sparrow는 겹침0 강제 → ~3배 헐거워짐 → Z1 대폭 악화. 배제.**
  적합한 건 sparrow-3d(우리 문제=x,y,layer 3D)뿐이나 크레인·시간 미모델 + 대규모 통합 필요.

## spread(반적층) 가설 테스트 — 반증
"2D 바닥 16~32%만 쓰니 펼치면 크레인 접근 쉬워져 대기↓" 가설로 spread 배치모드 구현:
| | bigleft | spread |
|---|---|---|
| prob_38 | 2359 | 2618 (+11%) |
| prob_37 | 487 | 564 (+16%) |
→ 반증. **뭉쳐 쌓기가 효율적**(바닥을 비워둬 이후 블록 수용). 펼치면 바닥 조기소진 → 대기↑.
  즉 62~74% 밀도는 bigleft 비효율이 아니라 **크레인 제약의 근본 한계**.

## 배치모드 전수 스윕 (순서=rank) — bigleft 최선
bigleft 2359 < leftbottom 2414 < bigcorner 2417 < flatbl 2433 < coreperi 2445 < spread 2618 < diagonal 2668.

## 종합 결론
측정이 2359가 이 문제구조의 실질 최적임을 강하게 시사:
- 밀도는 3D 레이어 packing에서 오고 bigleft가 이미 효율적(뭉쳐쌓기 최적, spread 반증).
- 62~74% 면적 상한 = 크레인 제약 근본한계(2D 여백 있어도 크레인이 못 넣음).
- order/mode/다변수/slack/window/spread/sparrow-2D 전부 rank+bigleft 못 이김.
- 유일 미소진 레버 = **sparrow-3d식 3D 불규칙 nesting**(크레인·시간 통합), 고위험·대규모.
