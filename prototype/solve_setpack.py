"""
OGC2026 프로토타입: 비트마스크 공간충돌그래프 + CP-SAT 스케줄링 (정확 수리계획)

정식화 (문서 bitmask_3d_approach.md 의 '경량 대안')
  - 공간배치는 열(column)로 열거하고 레이어별 비트마스크 occ[L], 크레인 수직그림자
    shadow[L]=OR_{lev<=L} occ[lev] 를 사전계산. 위치이동은 mask<<(dy*W+dx) (비트연산).
  - 각 블록은 정확히 한 공간배치 선택:  sum_k s[k] = 1.
  - 시간은 정수변수 EN_i, EX_i=EN_i+P_i.  지연 T_i>=EX_i-D_i.
  - 비트 AND 로 '공간충돌' 판정(같은레벨 occ&occ 또는 크레인 shadow&occ).
    공간충돌하는 두 배치가 모두 선택되면, 두 블록 시간구간은 서로 겹치면 안 됨
    (보수적: 겹치면 같은레벨/크레인 위반 → 시간분리 강제).
  - 시간창 프루닝: 가능한 [EN,EX) 구간이 절대 못 겹치는 블록쌍은 충돌검사 스킵.
  - CP-SAT 로 최적해 (휴리스틱 아님, 완전 탐색 솔버).

사용: python solve_setpack.py <instance.json> [n_sub] [sx] [sy] [maxwait] [timelimit]
"""
import sys, json, time, itertools, math
from shapely.geometry import Polygon, box
from ortools.sat.python import cp_model


# ---------- 기하 유틸 ----------
def aabb_offsets(block, o):
    xs = [v[0] for L in block["shape"][o]["layers"] for v in L]
    ys = [v[1] for L in block["shape"][o]["layers"] for v in L]
    return min(xs), max(xs), min(ys), max(ys)


def rasterize_mask(poly, W, theta=0.0):
    """래스터화: 단위셀 중 다각형이 (면적기준) theta 초과로 덮는 셀만 켠 비트마스크.
       theta=0 → 조금이라도 닿으면 점유(보수적/안전, mask-disjoint ⇒ polygon-disjoint).
       theta>0 → 가장자리 셀 제거로 발자국 축소(덜 보수적) → 조밀배치↑ 이나 안전보장 상실
                 (mask-disjoint 여도 원본 겹칠 수 있음 → 최종 정확검증/수리 필요)."""
    minx, miny, maxx, maxy = poly.bounds
    m = 0
    for cx in range(int(minx // 1) - 1, int(maxx // 1) + 2):
        for cy in range(int(miny // 1) - 1, int(maxy // 1) + 2):
            if poly.intersection(box(cx, cy, cx + 1, cy + 1)).area > theta + 1e-9:
                m |= (1 << (cy * W + cx))
    return m


# ---------- 공간 배치(placement) 열거 ----------
def build_placements(inst, subset, SX, SY, theta=0.0):
    """(블록,배향,베이)당 1회 래스터화(anchor) 후 위치이동은 비트 시프트.
       theta: 래스터화 보수성 knob (rasterize_mask 참고)."""
    bays = inst["bays"]
    Kmax = max(len(inst["blocks"][i]["shape"][0]["layers"]) for i in subset)
    per_block = {}
    for i in subset:
        b = inst["blocks"][i]
        Smax = max(b["bay_preferences"])
        plist = []
        for o in range(len(b["shape"])):
            ax0, ax1, ay0, ay1 = aabb_offsets(b, o)
            K = len(b["shape"][o]["layers"])
            for j, bay in enumerate(bays):
                W, H = bay["width"], bay["height"]
                xlo, xhi = math.ceil(-ax0 - 1e-9), math.floor(W - ax1 + 1e-9)
                ylo, yhi = math.ceil(-ay0 - 1e-9), math.floor(H - ay1 + 1e-9)
                xlo, ylo = max(0, xlo), max(0, ylo)
                if xlo > xhi or ylo > yhi:
                    continue
                base = {}
                for L in range(1, Kmax + 1):
                    if L <= K:
                        pl = Polygon([(vx + xlo, vy + ylo) for vx, vy in
                                      b["shape"][o]["layers"][L - 1]])
                        base[L] = rasterize_mask(pl, W, theta)
                    else:
                        base[L] = 0
                for x in range(xlo, xhi + 1, SX):
                    for y in range(ylo, yhi + 1, SY):
                        shift = (y - ylo) * W + (x - xlo)
                        occ = {L: base[L] << shift for L in range(1, Kmax + 1)}
                        shadow, acc = {}, 0
                        for L in range(1, Kmax + 1):
                            acc |= occ[L]; shadow[L] = acc
                        plist.append(dict(i=i, bay=j, o=o, x=x, y=y, occ=occ, shadow=shadow,
                                          prefloss=Smax - b["bay_preferences"][j],
                                          workload=b["workload"]))
        per_block[i] = plist
    return per_block, Kmax


def spatial_conflict(a, b, Kmax):
    """같은 베이 두 배치가 공간충돌(같은레벨 겹침 또는 크레인 그림자 겹침)하면 True."""
    if a["bay"] != b["bay"]:
        return False
    for L in range(1, Kmax + 1):
        if a["occ"][L] & b["occ"][L]:
            return True
    for L in range(1, Kmax + 1):
        if a["shadow"][L] & b["occ"][L]:  # a가 크레인될 때 b와 간섭
            return True
        if b["shadow"][L] & a["occ"][L]:  # b가 크레인될 때 a와 간섭
            return True
    return False


# ---------- 모델 & 풀이 ----------
def solve(inst, subset, SX, SY, MAXWAIT, timelimit=60):
    t0 = time.time()
    per_block, Kmax = build_placements(inst, subset, SX, SY)
    total = sum(len(v) for v in per_block.values())
    print(f"[place] {total} placements ({total//len(subset)}/block avg), Kmax={Kmax}, "
          f"build {time.time()-t0:.1f}s", flush=True)

    m = cp_model.CpModel()
    # 공간배치 선택변수
    svar = {}      # (i,idx) -> bool
    for i in subset:
        vs = [m.NewBoolVar(f"s_{i}_{k}") for k in range(len(per_block[i]))]
        for k, v in enumerate(vs):
            svar[(i, k)] = v
        m.Add(sum(vs) == 1)
    # 시간변수
    EN, EX, T = {}, {}, {}
    HORIZON = max(inst["blocks"][i]["due_date"] for i in subset) + \
        max(inst["blocks"][i]["processing_time"] for i in subset) + MAXWAIT + 5
    for i in subset:
        b = inst["blocks"][i]
        EN[i] = m.NewIntVar(b["release_time"], b["release_time"] + MAXWAIT, f"EN{i}")
        EX[i] = m.NewIntVar(0, HORIZON, f"EX{i}")
        m.Add(EX[i] == EN[i] + b["processing_time"])
        T[i] = m.NewIntVar(0, HORIZON, f"T{i}")
        m.Add(T[i] >= EX[i] - b["due_date"])

    # 공간충돌 그래프 → 시간분리 (시간창 프루닝 포함)
    t1 = time.time()
    n_pairs, n_conf = 0, 0
    for ia in range(len(subset)):
        for ib in range(ia + 1, len(subset)):
            i, jb = subset[ia], subset[ib]
            bi, bj = inst["blocks"][i], inst["blocks"][jb]
            # 가능한 최대 구간이 못 겹치면 스킵
            ai_lo, ai_hi = bi["release_time"], bi["release_time"] + MAXWAIT + bi["processing_time"]
            aj_lo, aj_hi = bj["release_time"], bj["release_time"] + MAXWAIT + bj["processing_time"]
            if min(ai_hi, aj_hi) <= max(ai_lo, aj_lo):
                continue
            print(f"    pair blk{i}-blk{jb}: {len(per_block[i])}x{len(per_block[jb])} "
                  f"placements (conf so far {n_conf})", flush=True)
            for ka, pa in enumerate(per_block[i]):
                for kb, pb in enumerate(per_block[jb]):
                    n_pairs += 1
                    if not spatial_conflict(pa, pb, Kmax):
                        continue
                    n_conf += 1
                    both = m.NewBoolVar(f"b_{i}_{ka}_{jb}_{kb}")
                    m.AddBoolAnd([svar[(i, ka)], svar[(jb, kb)]]).OnlyEnforceIf(both)
                    m.AddBoolOr([svar[(i, ka)].Not(), svar[(jb, kb)].Not()]).OnlyEnforceIf(both.Not())
                    before = m.NewBoolVar("bf")
                    m.Add(EX[i] <= EN[jb]).OnlyEnforceIf([both, before])
                    m.Add(EX[jb] <= EN[i]).OnlyEnforceIf([both, before.Not()])
    print(f"[conf] spatial pairs tested {n_pairs}, conflicts {n_conf}, "
          f"detect {time.time()-t1:.1f}s", flush=True)

    # 목적 w1*T + w2*Z2 + w3*prefloss  (정수화 스케일 1000, u_j 1000배)
    bays = inst["bays"]
    W = inst["weights"]
    avg = sum(bb["width"] * bb["height"] for bb in bays) / len(bays)
    u_s = [round(1000 * avg / (bb["width"] * bb["height"])) for bb in bays]
    SCALE = 1000
    WBj = []
    for j in range(len(bays)):
        terms = [u_s[j] * per_block[i][k]["workload"] * svar[(i, k)]
                 for i in subset for k in range(len(per_block[i])) if per_block[i][k]["bay"] == j]
        wb = m.NewIntVar(0, 10**9, f"WB{j}"); m.Add(wb == sum(terms)); WBj.append(wb)
    Gmax = m.NewIntVar(0, 10**9, "Gmax"); Gmin = m.NewIntVar(0, 10**9, "Gmin")
    for wb in WBj:
        m.Add(Gmax >= wb); m.Add(Gmin <= wb)
    Z2 = m.NewIntVar(0, 10**9, "Z2"); m.Add(Z2 >= Gmax - Gmin)
    prefloss = sum(per_block[i][k]["prefloss"] * svar[(i, k)]
                   for i in subset for k in range(len(per_block[i])))
    m.Minimize(SCALE * W["w1"] * sum(T[i] for i in subset)
               + SCALE * W["w3"] * prefloss + W["w2"] * Z2)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timelimit
    solver.parameters.num_search_workers = 4
    st = solver.Solve(m)
    print(f"[solve] status={solver.StatusName(st)} obj/1000={solver.ObjectiveValue()/1000:.1f} "
          f"time={solver.WallTime():.1f}s", flush=True)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    chosen = []
    for i in subset:
        for k in range(len(per_block[i])):
            if solver.Value(svar[(i, k)]) == 1:
                c = dict(per_block[i][k])
                c["EN"] = solver.Value(EN[i]); c["EX"] = solver.Value(EX[i])
                c["tard"] = solver.Value(T[i])
                chosen.append(c)
    return chosen


# ---------- 해 → 제출형식 & 정확 검증 ----------
def to_solution(chosen):
    ops = {}
    for c in chosen:
        ops.setdefault(str(c["EX"]), []).append(
            {"type": "EXIT", "block_id": c["i"], "bay_id": c["bay"]})
    for c in chosen:
        ops.setdefault(str(c["EN"]), []).append(
            {"type": "ENTRY", "block_id": c["i"], "bay_id": c["bay"],
             "x": c["x"], "y": c["y"], "orient_idx": c["o"]})
    for t in ops:
        ops[t].sort(key=lambda a: 0 if a["type"] == "EXIT" else 1)
    return {"operations": ops}


def exact_check(inst, chosen):
    """shapely 원본 다각형으로 컨테인먼트/같은레벨충돌/크레인/시간 검증 + 목적 재계산."""
    bays = inst["bays"]; errs = []

    def plp(c, L):
        b = inst["blocks"][c["i"]]
        if L > len(b["shape"][c["o"]]["layers"]):
            return None
        return Polygon([(vx + c["x"], vy + c["y"]) for vx, vy in
                        b["shape"][c["o"]]["layers"][L - 1]])

    for c in chosen:
        b = inst["blocks"][c["i"]]
        if c["EN"] < b["release_time"]:
            errs.append(f"blk{c['i']} EN<R")
        if c["EX"] - c["EN"] < b["processing_time"]:
            errs.append(f"blk{c['i']} 처리시간부족")
        W, H = bays[c["bay"]]["width"], bays[c["bay"]]["height"]
        for L in range(1, len(b["shape"][c["o"]]["layers"]) + 1):
            mnx, mny, mxx, mxy = plp(c, L).bounds
            if mnx < -1e-6 or mny < -1e-6 or mxx > W + 1e-6 or mxy > H + 1e-6:
                errs.append(f"blk{c['i']} L{L} 컨테인먼트위반")

    for a, b in itertools.combinations(chosen, 2):
        if a["bay"] != b["bay"]:
            continue
        lo, hi = max(a["EN"], b["EN"]), min(a["EX"], b["EX"])
        Ka = len(inst["blocks"][a["i"]]["shape"][a["o"]]["layers"])
        Kb = len(inst["blocks"][b["i"]]["shape"][b["o"]]["layers"])
        if lo < hi:
            for L in range(1, min(Ka, Kb) + 1):
                if plp(a, L).intersection(plp(b, L)).area > 1e-6:
                    errs.append(f"충돌 blk{a['i']}-blk{b['i']} L{L}")
        for (mv, ot, Km, Ko) in ((a, b, Ka, Kb), (b, a, Kb, Ka)):
            for t in (mv["EN"], mv["EX"] - 1):
                if ot["EN"] <= t < ot["EX"]:
                    for l1 in range(1, Km + 1):
                        for l2 in range(l1, Ko + 1):
                            if plp(mv, l1).intersection(plp(ot, l2)).area > 1e-6:
                                errs.append(f"크레인 blk{mv['i']}(L{l1})-blk{ot['i']}(L{l2})")

    Z1 = sum(c["tard"] for c in chosen)
    avg = sum(bb["width"] * bb["height"] for bb in bays) / len(bays)
    u = [avg / (bb["width"] * bb["height"]) for bb in bays]
    G = [sum(c["workload"] * u[j] for c in chosen if c["bay"] == j) for j in range(len(bays))]
    Z2 = max(G) - min(G) if len(bays) > 1 else 0
    Z3 = sum(c["prefloss"] for c in chosen)
    W = inst["weights"]
    return errs, dict(Z1=Z1, Z2=round(Z2, 2), Z3=Z3,
                      obj=round(W["w1"] * Z1 + W["w2"] * Z2 + W["w3"] * Z3, 1))


def main():
    path = sys.argv[1]
    n_sub = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    SX = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    SY = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    MAXWAIT = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    TL = int(sys.argv[6]) if len(sys.argv) > 6 else 60
    inst = json.load(open(path))
    subset = list(range(min(n_sub, len(inst["blocks"]))))
    print(f"=== {inst['name']} | blocks {subset[0]}..{subset[-1]} | bays={len(inst['bays'])} "
          f"SX={SX} SY={SY} MAXWAIT={MAXWAIT} TL={TL} ===", flush=True)
    chosen = solve(inst, subset, SX, SY, MAXWAIT, TL)
    if chosen is None:
        print("해 없음"); return
    errs, obj = exact_check(inst, chosen)
    print(f"[verify] 정확검증 위반 {len(errs)}건" +
          (f" (예: {errs[:3]})" if errs else " → FEASIBLE"), flush=True)
    print(f"[objective] {obj}", flush=True)
    for c in sorted(chosen, key=lambda c: c["i"]):
        print(f"  blk{c['i']}: bay{c['bay']} o{c['o']} ({c['x']},{c['y']}) "
              f"EN={c['EN']} EX={c['EX']} tard={c['tard']} prefloss={c['prefloss']}")
    json.dump(to_solution(chosen), open("solution_out.json", "w"), indent=1)
    print("[out] solution_out.json 저장", flush=True)


if __name__ == "__main__":
    main()
