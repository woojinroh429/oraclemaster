# coreperi를 v34에 통합 시도 — 정직한 현실 (구성-only는 과대평가)

## ratio 게이팅 정렬 (사용자 확인)
히든 P-클래스는 ratio(=peak _demand_ratio)로 게이팅: P1/P2<0.6, P5 0.6~0.7, P3/P4/P6>=0.7.
40개 전체 계산으로 스케일 일치 확인(prob_1~20 peak 0.28~0.48 <0.6, prob_21~40 대부분 >=0.7).

## 구성-only 비교: coreperi가 v34를 이기는 듯 보였음
_smallright_construct(coreperi) vs 전체 v34 algorithm()(NFP+ALNS+best-of):
- prob_33: coreperi Z1=810 obj6.51M vs v34 Z1=958 obj7.60M (+14.4%)
- prob_23: coreperi Z1=157 vs v34 Z1=174 (+6.6%)
=> "v34가 도달못하는 Z1을 coreperi가 낸다"고 보였음.

## 전체 파이프라인 net 비교: 대부분 흡수됨 (정직한 반전)
v34 워커 구조: smallright는 워커 1,2에서만(primary=bigleft,leftbottom), 여분 없음.
coreperi를 넣으려면 bigleft/leftbottom 중 하나를 밀어내야 함(=회귀 위험).
coreperi를 lane1 primary로 넣고 base(NO_COREPERI) vs +coreperi 측정(TL=100):
| 인스턴스 | base | +coreperi | 효과 |
|---|---|---|---|
| prob_23 | 157 | 157 | tie |
| prob_26 | 8.06M | 8.08M | -0.2% |
| prob_31 | 266 | 266 | tie |
| prob_32 | 353 | 353 | tie |
| prob_37 | 6.74M | 7.00M | **-3.9% 회귀** |
| prob_33 | 7.60M | 6.49M | +14.4% (별도) |
=> 5/6이 tie 또는 회귀. prob_33만 이김.

## 결론 (정직)
- **구성-only 비교는 과대평가.** 전체 파이프라인에선 v34의 ALNS/polish + 멀티워커 best-of가
  coreperi의 구성 이득을 대부분 흡수. bigleft를 coreperi로 교체하면 prob_33만 이기고
  prob_37/26 회귀(coreperi의 Z2/Z3가 나빠서).
- **primary 교체 = 안전하지 않음(회귀 실재).** 되돌림.
- 유일한 무회귀 배포: coreperi를 **추가 워커**로(best-of가 min 유지 -> 회귀 불가). 이는 여분
  코어 필요(NUM_PARALLEL_RUNS 상향, 서버 >=5코어). 4코어 샌드박스에선 검증 불가.
- 모드 정의(coreperi/bigright/bigtop)는 _smallright_construct에 남김(호출 안 하면 무해).

## 교훈
구성 단계 이득이 전체 파이프라인 이득과 다르다. 반드시 full algorithm()로 net 검증할 것.
