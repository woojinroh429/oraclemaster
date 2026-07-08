# 리서치 종합 — 고밀도·지연지배 2D packing+scheduling SOTA (인용 포함)

심층 리서치(103 에이전트, 소스 21개 fetch, 25 주장 검증, 24 confirmed/1 refuted) 결과.
질문: 과포화·지연(Z1) 지배 인스턴스를 위한 최신 파이프라인.

## 한 줄 결론
**순수 메타휴리스틱(ALNS)이 아니라 "분해-후-정확해결(decompose & solve exactly)" 아키텍처가
우세.** 문제를 **스케줄링/배정 마스터(베이 + 시작일 + 순서)** 와 **2D 패킹 feasibility
서브문제**로 쪼개고, 마스터는 CP/MIP로 풀고 패킹 엔진은 feasibility 오라클로만 쓴다.
= **Logic-Based Benders Decomposition (LBBD)**.

## 검증된 핵심 근거 (confidence: high)

1. **가장 직접적 SOTA = AM 네스팅+스케줄링 LBBD** — 비정형 부품, release/proc/due,
   누적 tardiness 최소화. 두 LBBD(MIP+CP, pure-CP) 중 **pure-CP가 최고**, 단일 CP 대비
   대폭 우세, 이전 정확법 대비 **1~2 자릿수 큰 인스턴스** 해결.
   *Nascimento, Silva, Antunes & Moniz (2024), EJOR 317(1):92-110.*

2. **우리가 목표한 "스케줄 마스터 + 2D패킹 feasibility 서브" 분해가 실증적으로 우세** —
   조합/중첩 Benders(master 배정·순서, sub 2D no-overlap)가 monolithic MIP·표준 LBBD보다
   빠르고 좋음. 중첩 LBBD가 Gurobi MIP보다 **최적해 50% 더** 확보.
   *EJOR S0377221724003394 (2024); EJOR S0377221725008069 (2025).*

3. **LBBD 가속 툴킷(2026)** — 2D패킹 p-batch 스케줄링 "일반"에 적용된다고 명시:
   동적 서브문제 근사, criticality-index로 마스터 유도, failure-directed ordering,
   greedy/irreducible 컷, infeasibility 재사용 → **>1자릿수 런타임 단축**.
   *EJOR S0377221726000767 (2026).*

4. **분해가 monolithic MIP를 안정적으로 이김** — 배정 master + cumulative feasibility sub
   (항공정비) LBBD가 MIP보다 평균 **4배 빠르게** 최적 증명, 지평 커질수록 우세.
   *Aramon Bajestani & Beck, JAIR 2014 (arXiv:1402.0582).*

5. ★**우리와 거의 같은 조선 문제 논문이 2단계 분해를 씀** — Phase1: 베이배정 + 처리
   시작일(=스케줄 백본), Phase2: 좌표 + 회전(=패킹). "이산변수가 많아 monolithic 최적은
   사실상 불가"라 명시. 목적 = 지각 블록수 + 베이/일 부하 불균형.
   *He, Hong, Kim (2024), Journal of Scheduling 27:409-422.*

6. **지연-인식 dense 구성 = ATC/ATCS 디스패칭 + NFP** — ATC의 lookahead를 **결정마다 동적
   재계산**(변동 혼잡에 자기적응 → 과포화에 적합). ATCS는 **셋업 의존이 유의할 때만** ATC를
   이김(우리는 셋업 없음 → ATC로 충분).
   *IJPE 106 (2007) 563-573; Zhang et al. ICTE 2011.*

7. **조선 공간일정 dense 구성 규칙 이식가능** — "standard-angle filling"(모든 변 각도 15°
   배수 → 사각형처럼 촘촘), "diagonal-fill"(BLF에 top-right 배치점도 고려).
   *CIE S0360835220306550 (2020); Kwon & Lee CIE S0360835215002296.*

8. **BAP/BACAP/QCSP가 세 구조를 독립 검증** — 연속 BAP=선박을 길이×시간 사각형(ALNS);
   BACAP=패턴 기반 set-partitioning; QCSP=LBBD(부하배정 master + 순서 sub).
   *Mauri et al. C&OR 70(2016); Iris et al. TR-E 81(2015); EJOR 2019 QCSP.*

9. **정확법을 LNS에 심는 법 = 탐욕 repair 대신 정확 recombination 오라클** — set-partitioning
   으로 축적된 패턴 풀을 최적 재조합 + DP 이웃. (= CP/MIP를 LNS repair 오라클로).
   *EURO J. Transp.&Log. S2192437621000121 (2021), VRPTW.*

10. (반례) 옛 조선 공간배정 = 3D-BPP + Guided Local Search(중첩 최소화), 정확법·ATCS 없음 —
    최신 분해/정확법이 넘어서려는 구 패러다임. *Caprace et al. (2013).*

## ⚠️ 정직한 두 가지 미스매치 (리서치가 명시)

1. **목적함수 미스매치**: 위 문헌은 전부 **비가중 지각수(ΣU_j) 또는 누적 tardiness(ΣT_j)**,
   또는 makespan. **우리는 가중 tardiness(w1·ΣT_i)**. → **아키텍처는 이식되지만, 가중지연
   지배에서의 성능은 직접 인용이 아니라 "합리적 전이"**. (가중은 마스터 목적 계수만 바뀜.)

2. **기하·시간 미스매치 (novel 리스크)**: 우리의 **크레인 차폐 + exit-blocking**(남이 크레인
   경로를 막아 블록이 체류 연장→지연)은 **surveyed 서브문제 어디에도 없음**. AM/BAP는 정적
   배치 또는 축정렬 사각형. → **우리 2D 패킹 feasibility 서브가 문헌보다 더 어렵다.**
   ★역으로: **우리 비트마스크/NFP 엔진이 이미 크레인+시공간을 정확히 처리** → 이게 자산.

## 미해결 질문 → 우리 결정
- Q: 가중 tardiness에서도 가속 유효? → 실험으로 확인(직접 근거 없음).
- Q: 크레인/blocking 서브문제 형식? → **우리 비트엔진을 그대로 오라클로** (문헌 공백을 이미 메움).
- Q: 100~300 과포화에서 마스터 tractable? → 안 되면 **롤링호라이즌 fix-and-optimize** 로.
- Q: 엔진 역할(Benders 컷 vs 정확 repair)? → 둘 다 실험. 우리 실측(탐욕 repair 실패)은 **정확 repair** 지지.

## 채택 파이프라인 (SOTA 반영)
```
구성: ATC(동적 lookahead) 디스패칭 + diagonal-fill/standard-angle NFP  [지연-인식 dense]
백본(Phase1/마스터): CP-SAT 스케줄링 — 베이배정 + 시작일 + (순서), 용량(면적/1D폭) 완화,
                    가중 tardiness 최소  ← 조기 지연을 정확 솔버가 결정 (ALNS엔 없던 층)
실현(Phase2/서브): 비트마스크·NFP 엔진으로 공간 실현 → 불가시 시간이동 or no-good 컷(Benders)
개선: 정확-repair LNS (이웃을 CP/MIP·set-partitioning으로 최적 재조합, 탐욕 아님)
확장: 250~300은 롤링호라이즌 relax-and-fix / fix-and-optimize
```
사용자님 ALNS+NFP는 **버리지 않고 기하 오라클/repair 엔진으로 재활용**, 그 위에 스케줄
백본을 얹는 것 — 리서치의 명시적 하이브리드 권고와 일치.
