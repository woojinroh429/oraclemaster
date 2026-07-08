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
import numpy as np
from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solve_setpack import build_placements, exact_check, to_solution  # 기하 재사용
import pricing_numba as pn

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


def find_bad_blocks(inst, chosen):
    """정확검증(shapely)에서 위반에 연루된 블록 id 집합을 반환."""
    from shapely.geometry import Polygon
    bays = inst["bays"]; bad = set()

    def plp(c, L):
        b = inst["blocks"][c["i"]]
        if L > len(b["shape"][c["o"]]["layers"]):
            return None
        return Polygon([(vx + c["x"], vy + c["y"]) for vx, vy in
                        b["shape"][c["o"]]["layers"][L - 1]])

    for c in chosen:                                  # 컨테인먼트/시간
        b = inst["blocks"][c["i"]]
        W, H = bays[c["bay"]]["width"], bays[c["bay"]]["height"]
        if c["EN"] < b["release_time"] or c["EX"] - c["EN"] < b["processing_time"]:
            bad.add(c["i"])
        for L in range(1, len(b["shape"][c["o"]]["layers"]) + 1):
            mnx, mny, mxx, mxy = plp(c, L).bounds
            if mnx < -1e-6 or mny < -1e-6 or mxx > W + 1e-6 or mxy > H + 1e-6:
                bad.add(c["i"])
    for a, b in itertools.combinations(chosen, 2):    # 충돌/크레인
        if a["bay"] != b["bay"]:
            continue
        lo, hi = max(a["EN"], b["EN"]), min(a["EX"], b["EX"])
        Ka = len(inst["blocks"][a["i"]]["shape"][a["o"]]["layers"])
        Kb = len(inst["blocks"][b["i"]]["shape"][b["o"]]["layers"])
        if lo < hi:
            for L in range(1, min(Ka, Kb) + 1):
                if plp(a, L).intersection(plp(b, L)).area > 1e-6:
                    bad.add(a["i"]); bad.add(b["i"])
        for (mv, ot, Km, Ko) in ((a, b, Ka, Kb), (b, a, Kb, Ka)):
            for t in (mv["EN"], mv["EX"] - 1):
                if ot["EN"] <= t < ot["EX"]:
                    for l1 in range(1, Km + 1):
                        for l2 in range(l1, Ko + 1):
                            if plp(mv, l1).intersection(plp(ot, l2)).area > 1e-6:
                                bad.add(mv["i"]); bad.add(ot["i"])
    return bad


def repair(inst, chosen, per_block_safe, Kmax, expand=False, cap=25):
    """repair: 위반 블록(+expand시 이웃)을 빼서 보수적(θ0) 마스크로 지연최소 재배치.
       주의(실측): 이웃 확장(expand=True)을 '탐욕' 재배치와 결합하면 대상만 늘어
       오히려 지연↑ (576k→979k). 이득 내려면 뺀 이웃을 '최적화'로 재해결해야 함.
       그래서 기본은 단순 repair(expand=False, 위반 블록만). 반환: (수리 chosen, 재배치수)."""
    bad = find_bad_blocks(inst, chosen)
    if not bad:
        return chosen, 0
    orig = {c["i"]: c for c in chosen}

    # 이웃 확장: bad 와 같은 베이·시간겹침·x근접(≤20) 인 kept 블록도 재배치 대상에
    remove = set(bad)
    if expand:
        cand = []
        for c in chosen:
            if c["i"] in bad:
                continue
            for bi in bad:
                bc = orig[bi]
                if (c["bay"] == bc["bay"] and c["EN"] < bc["EX"] and bc["EN"] < c["EX"]
                        and abs(c["x"] - bc["x"]) <= 20):
                    cand.append(c["i"]); break
        for i in cand:                                  # cap 한도 내에서 이웃 추가
            if len(remove) >= cap:
                break
            remove.add(i)

    def safe_p(i, bay, o, x, y):
        for p in per_block_safe[i]:
            if p["bay"] == bay and p["o"] == o and p["x"] == x and p["y"] == y:
                return p
        return None

    kept = [c for c in chosen if c["i"] not in remove]
    grid = {}
    for c in kept:                                      # 유지블록의 보수적 shadow 예약
        p = safe_p(c["i"], c["bay"], c["o"], c["x"], c["y"])
        if p is None:
            continue
        for day in range(c["EN"], c["EX"]):
            for L in range(1, Kmax + 1):
                key = (c["bay"], L, day)
                grid[key] = grid.get(key, 0) | p["shadow"][L]

    horizon = max(inst["blocks"][i]["due_date"] for i in range(len(inst["blocks"]))) + 60
    repaired = []
    # 재배치 순서: 납기 임박 우선 → 지연 크리티컬한 블록이 먼저 좋은 자리
    for i in sorted(remove, key=lambda i: inst["blocks"][i]["due_date"]):
        b = inst["blocks"][i]; P = b["processing_time"]; R = b["release_time"]
        prefbay = b["bay_preferences"].index(max(b["bay_preferences"]))
        x0 = orig[i]["x"]; bay0 = orig[i]["bay"]
        # 자리 후보: 선호베이·원위치 근접 우선으로 정렬(동률 지연시 변위 최소)
        plist = sorted(per_block_safe[i],
                       key=lambda q: (q["bay"] != prefbay, abs(q["x"] - x0)
                                      if q["bay"] == bay0 else 999, q["y"]))
        found = None
        for EN in range(R, horizon - P):                # EN 오름차 = 지연 최소
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
        if found is None:
            return None, len(remove)
        p, EN, EX = found
        for day in range(EN, EX):
            for L in range(1, Kmax + 1):
                key = (p["bay"], L, day)
                grid[key] = grid.get(key, 0) | p["shadow"][L]
        repaired.append(dict(i=i, bay=p["bay"], o=p["o"], x=p["x"], y=p["y"],
                             EN=EN, EX=EX, tard=max(0, EX - b["due_date"]),
                             prefloss=max(b["bay_preferences"]) - b["bay_preferences"][p["bay"]],
                             workload=b["workload"]))
    return kept + repaired, len(remove)


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

    # ---- Numba pricing 준비: 마스크 uint64 워드 팩킹 (블록당 1회) ----
    CELLMAX = max(bb["width"] * bb["height"] for bb in inst["bays"])
    WORDS = (CELLMAX + 63) // 64
    HORIZON = max(inst["blocks"][i]["due_date"] for i in subset) + \
        max(inst["blocks"][i]["processing_time"] for i in subset) + MAXWAIT + 5
    NDAYS = HORIZON + 2
    nbays = len(inst["bays"])
    tpk = time.time()
    packed = {}   # i -> (occ_w, shd_w, bay, prefloss)
    en_np = {}
    for i in subset:
        packed[i] = pn.pack_block(per_block[i], Kmax, WORDS)
        en_np[i] = np.array(en_opts[i], np.int64)
    mu_arr = np.zeros((nbays, Kmax, NDAYS, CELLMAX + 1), np.float64)
    print(f"[numba] pack {time.time()-tpk:.1f}s, CELLMAX={CELLMAX} WORDS={WORDS} NDAYS={NDAYS}",
          flush=True)

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
        tr = time.time()
        st = s.Solve()
        t_lp = time.time() - tr
        if st != pywraplp.Solver.OPTIMAL:
            print(f"  round {rnd}: LP status {st} (계속)", flush=True)
        pi = {i: assign_ct[i].dual_value() for i in subset}
        # μ dense 배열 채우기 (음수 듀얼만) — Numba 커널 입력
        mu_arr.fill(0.0)
        for key, ct in cell_ct.items():
            d = ct.dual_value()
            if d < -1e-9:
                mu_arr[key[0], key[1] - 1, key[2], key[3]] = d

        added = 0
        for i in subset:
            P = inst["blocks"][i]["processing_time"]
            due = inst["blocks"][i]["due_date"]
            occ_w, shd_w, bayarr, prefloss = packed[i]
            # Numba: 블록의 (배치 × EN) 감축비용 rc 일괄계산
            rcmat = pn.price_block(occ_w, shd_w, bayarr, prefloss, en_np[i],
                                   P, due, float(W["w1"]), float(W["w3"]),
                                   float(pi[i]), mu_arr)
            plist = per_block[i]; enlist = en_opts[i]
            cands = []  # (rc, p, EN, EX)
            for k in range(len(plist)):
                p = plist[k]
                if "fp" not in p:                       # 발자국(레이어 합) 캐시 1회
                    fp = 0
                    for L in range(1, Kmax + 1):
                        fp |= p["occ"][L]
                    p["fp"] = fp
                    p["fpc"] = bin(fp).count("1")
                for e in range(len(enlist)):
                    rc = rcmat[k, e]
                    if rc < -1e-6:
                        cands.append((rc, p, enlist[e], enlist[e] + P))
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
        print(f"  round {rnd}: LP obj={s.Objective().Value():.0f} cols={len(cols)} "
              f"cells={len(cell_ct)} added={added} | LP {t_lp:.1f}s price {time.time()-tr-t_lp:.1f}s",
              flush=True)
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

    # ---- repair 루프: 위반 있으면 보수적(θ0) 마스크로 위반 블록 재배치 ----
    if errs:
        tr = time.time()
        print("[repair] 위반 발생 → θ0(보수) 마스크로 재배치 준비 중...", flush=True)
        per_block_safe, _ = build_placements(inst, subset, SX, SY, 0.0)  # 안전 마스크
        new_chosen, nbad = repair(inst, chosen, per_block_safe, Kmax)
        if new_chosen is None:
            print(f"[repair] 재배치 실패(공간부족) — 원해 유지", flush=True)
        else:
            errs2, obj2 = exact_check(inst, new_chosen)
            print(f"[repair] {nbad}블록 재배치, {time.time()-tr:.1f}s → 위반 {len(errs2)}건"
                  + (" → FEASIBLE" if not errs2 else f" (예:{errs2[:2]})"), flush=True)
            print(f"[repair] 수리후 objective: {obj2}", flush=True)
            if not errs2:
                chosen, obj = new_chosen, obj2
    json.dump(to_solution(chosen), open("colgen_out.json", "w"), indent=1)
    print(f"[final] objective={obj}  → colgen_out.json", flush=True)


if __name__ == "__main__":
    main()
