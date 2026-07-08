# OGC 2026 — 블록 배치·스케줄링 수리계획(MIP) 모형 (v1: 단순화 버전)

> 목적: 문제(The Grand Shipyard Puzzle)를 **혼합정수계획(MIP)** 으로 1차 정식화한다.
> 이 버전은 계산량보다 **명료함**을 우선한다. 비볼록 다각형 충돌과 크레인 제약을
> **바운딩박스(AABB) 근사 + 시간 이산화**로 보수적으로 단순화했다.
> (근사이므로 최적성/타당성이 원문제와 완전히 동일하지는 않지만, 여기서 나온
> 배치·시각은 원문제에서도 항상 실행가능하다 — 아래 "단순화 가정" 참고.)

---

## 1. 집합 (Sets)

| 기호 | 의미 |
|---|---|
| $i \in N=\{1,\dots,n\}$ | 블록 |
| $j \in M=\{1,\dots,m\}$ | 베이(bay) |
| $o \in \{1,\dots,O_i\}$ | 블록 $i$ 의 배향(orientation) 옵션 |
| $t \in \mathcal{T}=\{0,1,\dots,H\}$ | 이산화된 날짜(day). $H$ = 계획 지평 |
| $(i,i') \in \mathcal{P}=\{(i,i'): i<i'\}$ | 블록 쌍 |

## 2. 파라미터 (Parameters)

**베이/블록 기본 데이터**

| 기호 | 의미 |
|---|---|
| $W_j, H_j$ | 베이 $j$ 의 폭·높이 |
| $R_i$ | 반입가능(release) 시각 |
| $D_i$ | 납기(due date) |
| $P_i$ | 처리시간(processing time) |
| $L_i$ | 작업부하(workload) |
| $S_{ij}$ | 블록 $i$ 를 베이 $j$ 에 배정할 때 선호도 ($\sum_j S_{ij}=100$) |
| $S^{\max}_i=\max_j S_{ij}$ | 블록 $i$ 의 최대 선호도 |
| $u_j=\dfrac{(\sum_{k\in M}W_kH_k)/m}{W_jH_j}$ | 베이 $j$ 의 부하 가중치(작은 베이일수록 큼) |
| $w_1,w_2,w_3$ | 목적함수 가중치 |

**지오메트리 전처리 (핵심 단순화)** — 각 블록 $i$, 배향 $o$ 에 대해, 모든 레이어의
모든 꼭짓점(기준점 기준 상대좌표)을 훑어 **축정렬 바운딩박스(AABB)** 를 미리 계산한다.

| 기호 | 의미 (기준점 대비 오프셋, 상수) |
|---|---|
| $\alpha^-_{io},\ \alpha^+_{io}$ | 배향 $o$ 에서 $x$ 방향 최소/최대 오프셋 |
| $\beta^-_{io},\ \beta^+_{io}$ | 배향 $o$ 에서 $y$ 방향 최소/최대 오프셋 |

즉 기준점을 $(x_i,y_i)$ 에 두면 블록은 사각형
$[\,x_i+\alpha^-_{io},\ x_i+\alpha^+_{io}\,]\times[\,y_i+\beta^-_{io},\ y_i+\beta^+_{io}\,]$ 를 차지한다.
(예: prob_1 블록0, 배향0은 $\alpha^-=0,\alpha^+=5.79,\beta^-=-0.34,\beta^+=15.34$)

**Big-M 상수**: $M_x=\max_j W_j,\quad M_y=\max_j H_j,\quad$ 시간에는 $H$ 사용.

**계획 지평**: $H=\max_i D_i+\sum_i P_i$ (충분히 큰 상한. 실무상 훨씬 작게 잡아도 됨).

## 3. 결정변수 (Decision variables)

| 변수 | 형 | 의미 |
|---|---|---|
| $a_{ij}\in\{0,1\}$ | 이진 | 블록 $i$ 를 베이 $j$ 에 배정 |
| $v_{io}\in\{0,1\}$ | 이진 | 블록 $i$ 가 배향 $o$ 선택 |
| $x_i,\ y_i \in \mathbb{Z}_{\ge0}$ | 정수 | 기준점 위치 (제출형식이 정수 요구) |
| $\mathrm{EN}_i,\ \mathrm{EX}_i \in \mathbb{Z}_{\ge0}$ | 정수 | 반입(ENTRY)·반출(EXIT) 시각 |
| $z_{it}\in\{0,1\}$ | 이진 | 블록 $i$ 가 날짜 $t$ 에 베이 안에 있음 ($\mathrm{EN}_i\le t<\mathrm{EX}_i$) |
| $T_i \ge 0$ | 연속 | 지연(tardiness) |
| $\sigma_{ii'},\ \tau_{ii'}\in\{0,1\}$ | 이진 | 쌍 $(i,i')$ 이 같은 베이 / 시간중첩 여부 |
| $\delta_{ii'}\in\{0,1\}$ | 이진 | 쌍을 공간분리해야 함(같은 베이 ∧ 시간중첩) |
| $L^{ii'},R^{ii'},B^{ii'},A^{ii'}\in\{0,1\}$ | 이진 | 분리 방향(좌/우/아래/위) 선택 |
| $G_{\max},G_{\min}\ge0,\ Z_2\ge0$ | 연속 | 부하불균형 보조변수 |

**보조 선형식(정의만, 변수 아님)** — 실제 차지영역의 경계:
$$
x^{-}_i=x_i+\!\sum_o\alpha^-_{io}v_{io},\quad
x^{+}_i=x_i+\!\sum_o\alpha^+_{io}v_{io},\quad
y^{-}_i=y_i+\!\sum_o\beta^-_{io}v_{io},\quad
y^{+}_i=y_i+\!\sum_o\beta^+_{io}v_{io}.
$$

## 4. 목적함수 (Objective)

$$
\min\quad w_1\underbrace{\sum_{i\in N}T_i}_{Z_1}\;+\;w_2\,Z_2\;+\;w_3\underbrace{\sum_{i\in N}\sum_{j\in M}\bigl(S^{\max}_i-S_{ij}\bigr)a_{ij}}_{Z_3}
$$

- $Z_1$: 총 지연
- $Z_2$: 최대 정규화 부하불균형 (아래 (C13)–(C15))
- $Z_3$: 총 선호도 손실

## 5. 제약식 (Constraints)

### 5.1 배정·배향
$$
\sum_{j\in M} a_{ij}=1 \quad\forall i \tag{C1}
$$
$$
\sum_{o=1}^{O_i} v_{io}=1 \quad\forall i \tag{C2}
$$
(각 블록은 정확히 한 베이·한 배향. ENTRY/EXIT 각 1회는 변수 $\mathrm{EN}_i,\mathrm{EX}_i$ 가 하나씩이므로 자동 충족.)

### 5.2 시간 제약
$$
\mathrm{EN}_i \ge R_i \quad\forall i \tag{C3}
$$
$$
\mathrm{EX}_i-\mathrm{EN}_i \ge P_i \quad\forall i \tag{C4}
$$

**점유 지시자 $z_{it}$ 연결** ( $z_{it}=1 \Leftrightarrow \mathrm{EN}_i\le t<\mathrm{EX}_i$ ):
$$
t \ge \mathrm{EN}_i - H\,(1-z_{it}) \quad\forall i,t \tag{C5}
$$
$$
t \le \mathrm{EX}_i - 1 + H\,(1-z_{it}) \quad\forall i,t \tag{C6}
$$
$$
\sum_{t\in\mathcal{T}} z_{it} = \mathrm{EX}_i-\mathrm{EN}_i \quad\forall i \tag{C7}
$$
> (C5)–(C6)은 "구간 밖이면 $z=0$"을, (C7)은 딱 $\mathrm{EX}_i-\mathrm{EN}_i$ 일만 켜지도록 강제한다.
> 켜질 수 있는 자리가 구간 안뿐이므로 결과적으로 구간 전체가 정확히 1이 된다.

**지연**:
$$
T_i \ge \mathrm{EX}_i - D_i,\qquad T_i \ge 0 \quad\forall i \tag{C8}
$$

### 5.3 공간 제약 — 베이 포함 (Containment)
$$
x^{-}_i \ge 0,\qquad x^{+}_i \le \sum_{j} W_j\,a_{ij} \quad\forall i \tag{C9}
$$
$$
y^{-}_i \ge 0,\qquad y^{+}_i \le \sum_{j} H_j\,a_{ij} \quad\forall i \tag{C10}
$$

### 5.4 공간 제약 — 비중첩 (No-overlap, 쌍별 disjunctive)

**분리 필요 여부 판별** — 같은 베이이고 시간중첩이면 $\delta=1$:
$$
\sigma_{ii'} \ge a_{ij}+a_{i'j}-1 \quad\forall (i,i')\in\mathcal{P},\ \forall j \tag{C11a}
$$
$$
\tau_{ii'} \ge z_{it}+z_{i't}-1 \quad\forall (i,i')\in\mathcal{P},\ \forall t \tag{C11b}
$$
$$
\delta_{ii'} \ge \sigma_{ii'}+\tau_{ii'}-1 \quad\forall (i,i')\in\mathcal{P} \tag{C11c}
$$

**4방향 분리 disjunction** — 분리가 필요하면 최소 한 방향이 켜져야 함:
$$
L^{ii'}+R^{ii'}+B^{ii'}+A^{ii'} \ge \delta_{ii'} \quad\forall (i,i')\in\mathcal{P} \tag{C12a}
$$
$$
x^{+}_i \le x^{-}_{i'} + M_x\,(1-L^{ii'}) \qquad\text{(}i\text{가 }i'\text{ 왼쪽)} \tag{C12b}
$$
$$
x^{+}_{i'} \le x^{-}_i + M_x\,(1-R^{ii'}) \qquad\text{(}i\text{가 }i'\text{ 오른쪽)} \tag{C12c}
$$
$$
y^{+}_i \le y^{-}_{i'} + M_y\,(1-B^{ii'}) \qquad\text{(}i\text{가 }i'\text{ 아래)} \tag{C12d}
$$
$$
y^{+}_{i'} \le y^{-}_i + M_y\,(1-A^{ii'}) \qquad\text{(}i\text{가 }i'\text{ 위)} \tag{C12e}
$$

### 5.5 부하 불균형 $Z_2$
베이별 가중 부하 $G_j=u_j\sum_i L_i a_{ij}$ 에 대해:
$$
G_{\max} \ge u_j\textstyle\sum_i L_i a_{ij} \quad\forall j \tag{C13}
$$
$$
G_{\min} \le u_j\textstyle\sum_i L_i a_{ij} \quad\forall j \tag{C14}
$$
$$
Z_2 \ge G_{\max}-G_{\min} \tag{C15}
$$
> $\max_{j_1\neq j_2}|G_{j_1}-G_{j_2}| = G_{\max}-G_{\min}$. 원식의 올림($\lceil\cdot\rceil$)은 $Z_2$ 를
> 정수로 두면 최소화 압력에 의해 자동 처리된다(선택).

---

## 6. 단순화 가정 및 근사의 타당성

1. **바운딩박스(AABB) 근사.** 비볼록 다각형 대신 각 블록을 배향별 최소 외접
   사각형 하나로 본다. 사각형이 안 겹치면 실제 다각형(모든 레이어)도 반드시 안
   겹치므로 **원문제에 대해 항상 실행가능(보수적)**. 대신 실제로는 배치 가능한
   조밀한 해를 놓칠 수 있다(최적성 손실).

2. **레이어/크레인 제약 자동 충족.** 블록을 (레이어 구분 없는) 단일 사각형으로
   보고 *공존하는 모든 날*에 대해 비중첩을 걸었으므로, "동일 레벨 충돌"과 "크레인
   수직 간섭"(C(i₁,l₁,·,i₂,l₂,·)=0, l₁≤l₂) 은 자동으로 만족된다. 즉 크레인 제약을
   별도 제약식으로 넣지 않아도 된다 — v1을 단순하게 만드는 핵심 지점.

3. **반개구간 $[\mathrm{EN}_i,\mathrm{EX}_i)$ + EXIT 우선.** 같은 날 EXIT가 ENTRY보다 먼저
   수행된다는 규칙은 반개구간으로 자동 반영된다: $i$ 가 $t$ 에 나가고 $i'$ 가 $t$ 에
   들어오면 두 블록은 어떤 날도 공유하지 않아 충돌 제약이 걸리지 않는다.
   따라서 하루 안의 연산 순서를 명시적으로 모델링하지 않아도 된다(출력 시 EXIT를
   ENTRY보다 앞에 나열).

4. **시간 이산화.** 모든 시각 데이터가 정수이므로 날짜를 정수 격자로 둔다.
   지평 $H$ 는 느슨한 상한이며, 인스턴스별로 $\max_i D_i + (\text{여유})$ 수준으로
   줄이면 $z_{it}$ 수와 (C11b) 제약이 크게 감소한다.

---

## 7. 규모 및 다음 단계 메모

- 학습 인스턴스: 블록 $n=100\!\sim\!300$, 베이 $m=2\!\sim\!5$, 레이어 $K\le4$, 배향 $O\le8$.
- 쌍별 제약 (C11b), (C12)가 $O(n^2)$, 시간 결합 (C11b)가 $O(n^2 H)$ 로 지배적.
  → v1은 "정식화 명료화"가 목적이므로 이대로 두되, 실전 규모에서는:
  - **시간창 프루닝**: $[R_i,\ \text{도달가능한 } \mathrm{EX}]$ 가 겹치지 않는 쌍은 (C11b)/(C12) 생략.
  - **베이 사전배정**: 선호도/부하 기반 휴리스틱으로 $a_{ij}$ 일부 고정 후 베이별 분해.
  - **롤링 호라이즌 / 열생성**으로 $z_{it}$ 축소.
  - AABB 대신 **No-Fit-Polygon** 이나 격자 기반 배치로 근사를 정밀화(최적성 회복).
