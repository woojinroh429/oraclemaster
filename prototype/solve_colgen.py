"""
OGC2026 프로토타입 ②: 열생성(Column Generation, price-and-branch)

완전열거(solve_setpack)는 충돌쌍이 O(배치^2)로 폭증했다. 열생성은 이를 우회한다:
  - 마스터 LP(GLOP): 배정 Σ_c p_c = 1 (블록별),  시공간 셀 용량 Σ_c p_c <= 1 (셀별).
    → 비겹침을 '쌍(pair)'이 아니라 '셀(cell)' 제약으로 표현 (쌍대값이 깔끔).
  - Pricing: 블록별로 감축비용 rc = cost_c - pi_i - Σ_{cell∈c} mu_cell 최소 열을
    비트마스크로 탐색해 추가. mu_cell<=0 이라 -Σmu 는 혼잡 페널티.
  - 크레인은 셀에 shadow-augmented(입출고일 경계에 수직그림자 추가)로 정확 반영.
  - LP 최적(음의 rc 없음)까지 열을 모은 뒤, 생성된 열로 정수 set-partitioning(CP-SAT)
    을 풀어 실행가능 정수해를 얻고 shapely 로 정확검증.

주: 이는 price-and-branch(=LP열생성 후 정수화)로, 완전 branch-and-price(분수해 분지까지)
    는 아니다. 목적은 '완전열거의 벽 돌파'를 실증하는 것.

사용: python solve_colgen.py <instance.json> [n_sub] [sx] [sy] [maxwait] [en_step] [rounds] [tl]
"""
import sys, os, json, time, itertools
from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solve_setpack import build_placements, exact_check, to_solution  # 기하 재사용

BIG = 10**9  # 더미(미배치) 열 비용


def cells_of(p, EN, EX, Kmax):
    """열이 점유하는 시공간 셀 리스트 (bay,L,day,bit). 경계일은 크레인 그림자 사용."""
    out = []
    for day in range(EN, EX):
        boundary = (day == EN or day == EX - 1)
        for L in range(1, Kmax + 1):
            mask = p["shadow"][L] if boundary else p["occ"][L]
            mm = mask
            while mm:
                b = (mm & -mm).bit_length() - 1
                out.append((p["bay"], L, day, b))
                mm &= mm - 1
    return out


def greedy_seed(inst, subset, per_block, Kmax):
    """① 무충돌 배치 1벌을 직접 구성(EDD 순, 비트마스크 fit-검사). 크레인 안전을 위해
       각 블록의 수직그림자(shadow)를 체류기간 내내 예약 → 보수적이지만 실행가능 보장.
       반환: [(i, p, EN)] (정수해가 절대 INFEASIBLE 안 나게 하는 시드 열). 실패 시 None."""
    order = sorted(subset, key=lambda i: inst["blocks"][i]["due_date"])
    grid = {}   # (bay,L,day) -> 누적 예약 마스크
    horizon = max(inst["blocks"][i]["due_date"] for i in subset) + 40
    placed = []
    for i in order:
        b = inst["blocks"][i]; P = b["processing_time"]; R = b["release_time"]
        prefbay = b["bay_preferences"].index(max(b["bay_preferences"]))
        plist = sorted(per_block[i], key=lambda q: (q["bay"] != prefbay, q["x"], q["y"]))
        found = None
        for EN in range(R, horizon - P):
            EX = EN + P
            for p in plist:
                ok = True
                for day in range(EN, EX):
                    for L in range(1, Kmax + 1):
                        if p["shadow"][L] & grid.get((p["bay"], L, day), 0):
                            ok = False; break
                    if not ok:
                        break
                if ok:
                    found = (p, EN, EX); break
            if found:
                break
        if not found:
            return None
        p, EN, EX = found
        for day in range(EN, EX):
            for L in range(1, Kmax + 1):
                key = (p["bay"], L, day)
                grid[key] = grid.get(key, 0) | p["shadow"][L]
        placed.append((i, p, EN))
    return placed


def main():
    path = sys.argv[1]
    n_sub = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    SX = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    SY = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    MAXWAIT = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    EN_STEP = int(sys.argv[6]) if len(sys.argv) > 6 else 2
    ROUNDS = int(sys.argv[7]) if len(sys.argv) > 7 else 40
    TL = int(sys.argv[8]) if len(sys.argv) > 8 else 60
    THETA = float(sys.argv[9]) if len(sys.argv) > 9 else 0.0
    TOPK = int(sys.argv[10]) if len(sys.argv) > 10 else 6
    inst = json.load(open(path))
    subset = list(range(min(n_sub, len(inst["blocks"]))))
    W = inst["weights"]
    print(f"=== {inst['name']} | blocks 0..{subset[-1]} | bays={len(inst['bays'])} "
          f"SX={SX} SY={SY} MAXWAIT={MAXWAIT} EN_STEP={EN_STEP} THETA={THETA} ===", flush=True)

    t0 = time.time()
    per_block, Kmax = build_placements(inst, subset, SX, SY, THETA)
    avg_fp = sum(bin(p["occ"][1]).count("1") for v in per_block.values() for p in v) \
        / max(1, sum(len(v) for v in per_block.values()))
    print(f"[raster] theta={THETA} avg L1 footprint cells={avg_fp:.1f}", flush=True)
    tot = sum(len(v) for v in per_block.values())
    print(f"[place] {tot} spatial placements ({tot//len(subset)}/block), Kmax={Kmax}, "
          f"build {time.time()-t0:.1f}s", flush=True)

    # 블록별 시간옵션 EN 후보
    en_opts = {}
    for i in subset:
        b = inst["blocks"][i]
        en_opts[i] = list(range(b["release_time"], b["release_time"] + MAXWAIT + 1, EN_STEP))

    # ---- 마스터 LP (GLOP) ----
    s = pywraplp.Solver.CreateSolver("GLOP")
    s.SuppressOutput()
    assign_ct = {i: s.Constraint(1, 1, f"a{i}") for i in subset}  # Σ p = 1
    cell_ct = {}   # cellkey -> Constraint(0,1)
    cols = []      # 각 열: dict(i,p,EN,EX,cost,cells,var)

    def get_cell_ct(key):
        c = cell_ct.get(key)
        if c is None:
            c = s.Constraint(0, 1, "c")
            cell_ct[key] = c
        return c

    def add_column(i, p, EN):
        EX = EN + inst["blocks"][i]["processing_time"]
        tard = max(0, EX - inst["blocks"][i]["due_date"])
        cost = W["w1"] * tard + W["w3"] * p["prefloss"]
        var = s.NumVar(0, s.infinity(), "")
        s.Objective().SetCoefficient(var, float(cost))
        assign_ct[i].SetCoefficient(var, 1)
        cl = cells_of(p, EN, EX, Kmax)
        for key in cl:
            get_cell_ct(key).SetCoefficient(var, 1)
        cols.append(dict(i=i, p=p, EN=EN, EX=EX, tard=tard, cost=cost, cells=cl, var=var))
    s.Objective().SetMinimization()

    # 더미(미배치) 열. Big-M 은 '실제 열 최대비용의 몇 배'로 (과대한 1e9는 LP 수치불안정 유발).
    maxdue = max(inst["blocks"][i]["due_date"] for i in subset)
    BIGM = 10.0 * (W["w1"] * maxdue + W["w3"] * 100)
    print(f"[bigM] {BIGM:.3g}", flush=True)
    for i in subset:
        dvar = s.NumVar(0, s.infinity(), f"dummy{i}")
        s.Objective().SetCoefficient(dvar, float(BIGM))
        assign_ct[i].SetCoefficient(dvar, 1)
        seeds = per_block[i][::max(1, len(per_block[i]) // 4)][:4]  # 위치 몇 개 분산
        for p in seeds:
            for EN in en_opts[i][:2]:
                add_column(i, p, EN)
    # ① greedy feasibility 시드: 무충돌 1벌을 열로 추가 → 정수 INFEASIBLE 방지
    tg = time.time()
    gseed = greedy_seed(inst, subset, per_block, Kmax)
    if gseed is None:
        print("[greedy] 실패(공간부족?) — 시드 없이 진행", flush=True)
    else:
        gt = sum(max(0, EN + inst["blocks"][i]["processing_time"] - inst["blocks"][i]["due_date"])
                 for (i, p, EN) in gseed)
        for (i, p, EN) in gseed:
            add_column(i, p, EN)
        print(f"[greedy] 시드 {len(gseed)}블록 배치 성공, greedy 총지연 Z1={gt}, "
              f"{time.time()-tg:.1f}s", flush=True)
    print(f"[init] seed columns {len(cols)}", flush=True)

    # ---- 열생성 루프 ----
    for rnd in range(ROUNDS):
        st = s.Solve()
        if st != pywraplp.Solver.OPTIMAL:
            print(f"  round {rnd}: LP status {st} (계속)", flush=True)
        pi = {i: assign_ct[i].dual_value() for i in subset}
        # mu 를 (bay,L,day)->{bit:val} 로 정리 (음수만 의미)
        mu_by = {}
        for key, ct in cell_ct.items():
            d = ct.dual_value()
            if d < -1e-9:
                mu_by.setdefault((key[0], key[1], key[2]), {})[key[3]] = d

        added = 0
        for i in subset:
            P = inst["blocks"][i]["processing_time"]
            cands = []  # (rc, p, EN, EX)  감축비용 음수인 후보들
            for p in per_block[i]:
                if "fp" not in p:                       # 발자국(레이어 합) 캐시 1회
                    fp = 0
                    for L in range(1, Kmax + 1):
                        fp |= p["occ"][L]
                    p["fp"] = fp
                    p["fpc"] = bin(fp).count("1")
                for EN in en_opts[i]:
                    EX = EN + P
                    tard = max(0, EX - inst["blocks"][i]["due_date"])
                    cost = W["w1"] * tard + W["w3"] * p["prefloss"]
                    smu = 0.0
                    for day in range(EN, EX):
                        boundary = (day == EN or day == EX - 1)
                        for L in range(1, Kmax + 1):
                            dd = mu_by.get((p["bay"], L, day))
                            if not dd:
                                continue
                            mask = p["shadow"][L] if boundary else p["occ"][L]
                            for bit, val in dd.items():
                                if (mask >> bit) & 1:
                                    smu += val
                    rc = cost - pi[i] - smu
                    if rc < -1e-6:
                        cands.append((rc, p, EN, EX))
            # ⑦ top-k + NMS: 최선은 항상 채택, 차선은 시공간 겹침 30% 초과면 스킵
            cands.sort(key=lambda c: c[0])
            selected = []
            for (rc, p, EN, EX) in cands:
                dup = False
                for (sp, sEN, sEX) in selected:
                    if EN < sEX and sEN < EX and sp["bay"] == p["bay"]:  # 시간겹침 & 같은베이
                        if (bin(p["fp"] & sp["fp"]).count("1") / max(1, p["fpc"])) > 0.3:
                            dup = True
                            break
                if dup:
                    continue
                add_column(i, p, EN)
                selected.append((p, EN, EX))
                added += 1
                if len(selected) >= TOPK:
                    break
        if rnd % 5 == 0 or added == 0:
            print(f"  round {rnd}: LP obj={s.Objective().Value():.0f} cols={len(cols)} "
                  f"cells={len(cell_ct)} added={added}", flush=True)
        if added == 0:
            print(f"[cg] LP 최적 (음의 감축비용 없음) at round {rnd}, "
                  f"LP obj={s.Objective().Value():.0f}", flush=True)
            break

    # ---- 정수 RMP (CP-SAT, 생성열만) ----
    t1 = time.time()
    m = cp_model.CpModel()
    xvar = [m.NewBoolVar(f"x{k}") for k in range(len(cols))]
    bycol = {}
    for k, c in enumerate(cols):
        bycol.setdefault(c["i"], []).append(k)
    for i in subset:
        m.Add(sum(xvar[k] for k in bycol[i]) == 1)
    cellmap = {}
    for k, c in enumerate(cols):
        for key in c["cells"]:
            cellmap.setdefault(key, []).append(k)
    for key, ks in cellmap.items():
        if len(ks) > 1:
            m.Add(sum(xvar[k] for k in ks) <= 1)
    # Z2 (부하 불균형)
    bays = inst["bays"]
    avg = sum(bb["width"] * bb["height"] for bb in bays) / len(bays)
    u_s = [round(1000 * avg / (bb["width"] * bb["height"])) for bb in bays]
    WBj = []
    for j in range(len(bays)):
        terms = [u_s[j] * cols[k]["p"]["workload"] * xvar[k]
                 for k in range(len(cols)) if cols[k]["p"]["bay"] == j]
        wb = m.NewIntVar(0, 10**9, f"WB{j}"); m.Add(wb == sum(terms)); WBj.append(wb)
    Gmax = m.NewIntVar(0, 10**9, "Gx"); Gmin = m.NewIntVar(0, 10**9, "Gn")
    for wb in WBj:
        m.Add(Gmax >= wb); m.Add(Gmin <= wb)
    Z2 = m.NewIntVar(0, 10**9, "Z2"); m.Add(Z2 >= Gmax - Gmin)
    m.Minimize(1000 * sum(W["w1"] * cols[k]["tard"] * xvar[k] for k in range(len(cols)))
               + 1000 * sum(W["w3"] * cols[k]["p"]["prefloss"] * xvar[k] for k in range(len(cols)))
               + W["w2"] * Z2)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = TL
    solver.parameters.num_search_workers = 4
    stt = solver.Solve(m)
    print(f"[int] status={solver.StatusName(stt)} obj/1000={solver.ObjectiveValue()/1000:.1f} "
          f"time={time.time()-t1:.1f}s", flush=True)
    if stt not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("정수해 없음"); return
    chosen = []
    for k in range(len(cols)):
        if solver.Value(xvar[k]) == 1:
            c = cols[k]
            chosen.append(dict(i=c["i"], bay=c["p"]["bay"], o=c["p"]["o"],
                               x=c["p"]["x"], y=c["p"]["y"], EN=c["EN"], EX=c["EX"],
                               tard=c["tard"], prefloss=c["p"]["prefloss"],
                               workload=c["p"]["workload"]))
    errs, obj = exact_check(inst, chosen)
    print(f"[verify] 정확검증 위반 {len(errs)}건" +
          (f" (예: {errs[:3]})" if errs else " → FEASIBLE"), flush=True)
    print(f"[objective] {obj}", flush=True)
    json.dump(to_solution(chosen), open("colgen_out.json", "w"), indent=1)
    print("[out] colgen_out.json", flush=True)


if __name__ == "__main__":
    main()
