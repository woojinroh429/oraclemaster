# 배치 방향 best-of — 중밀도에서 실측 Z1 이득 (실제 엔진)

## 동기
bigleft가 모든 인스턴스에서 최선일 이유 없음. 좌우 미러(bigright), 상단쌓기(bigtop),
core-periphery를 추가해 인스턴스별 승자를 실측 -> best-of로 무회귀 이득.

## 추가 모드 (_smallright_construct, place_custom)
- bigright: 큰블록 우측벽 클러스터 sc=(h, bw-(wx+w), wy, j), 작은블록 free-span 유지
- bigtop:   큰블록 상단 클러스터 sc=(h, bh-(wy+h), wx, j), 작은블록 free-span 유지
- coreperi: 장기체류 대형=외곽, 나머지 bigleft (기존)

## 결과 (순서=rank 고정, DL 200~220s)
| 인스턴스 | bigleft | bigright | bigtop | coreperi | best-of | 이득 |
|---|---|---|---|---|---|---|
| prob_25 | 366 | **348** | 456 | 367 | 348 | -4.9% |
| prob_26 | 605 | 579 | 609 | **571** | 571 | -5.6% |
| prob_27 | **1564** | 1597 | 1696 | 1745 | 1564 | 0 |
| prob_33 | 981 | 969 | 961 | **810** | 810 | **-17.4%** |
| prob_37 | 487 | 502 | 487 | **477** | 477 | -2.1% |
| prob_38 | **2359** | 2507 | 2451 | 2445 | 2359 | 0 |
| prob_39 | **490** | 492 | 574 | 611 | 490 | 0 |
| prob_40 | **2416** | 2505 | 2430 | 2504 | 2416 | 0 |

## 결론
- 단일 방향 지배 없음. best-of{bigleft,bigright,bigtop,coreperi} => 4/8 이득, 무회귀.
- **중밀도(25/26/33/37)가 헤드룸**: bigright/coreperi 승. prob_33 -17%는 큰 win.
- 고밀도(38/39/40)는 bigleft 유지(포화). => 방향 best-of는 고밀도 무해, 중밀도 이득.
- 주의: 구성단계 Z1(ALNS 전). best-of가 무회귀 보장 + ALNS에 더 좋은 시드 제공.

## 배포 (기존 best-of 구조에 모드 추가만)
algorithm()의 구성 워커 풀에 mode="bigright"/"bigtop"/"coreperi" 워커를 추가하고
best-of(min objective)에 포함. 기존 bigleft 워커 유지 => 회귀 불가, 중밀도 이득 포착.
저밀도(Z1=0)엔 Z2/Z3로 tie-break되므로 방향이 Z2도 바꿈(예: prob25 bigright Z2 1897->763).
