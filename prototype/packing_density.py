"""밀도 실험: 한 베이에 블록을 최대한 채워 배치규칙별 밀도를 비교.
   3D 비트 엔진(footprint 마스크 AND)로 충돌 판정. 시간축 무시(단일 공존 스냅샷),
   순수 2D 공간 밀도만 측정 → 배치규칙(first-fit vs Bottom-Left)의 효과를 격리.

사용: python packing_density.py <instance.json> [bay_idx] [n_try] [sx] [sy]
"""
import sys, json, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from solve_setpack import build_placements


def footprint(p, Kmax):
    fp = 0
    for L in range(1, Kmax + 1):
        fp |= p["occ"][L]
    return fp


def pack(blocks_placements, rule, order, W, H):
    """blocks_placements: [(block_id, [placement...])].  rule: 'firstfit'|'blf'.
       order: 'input'|'area'.  반환: (placed, occ_area, used_cells_mask)."""
    items = list(blocks_placements)
    if order == "area":
        # 대표 면적(첫 배치 footprint popcount) 큰 순
        items.sort(key=lambda kv: -bin(kv[1][0]["fp"]).count("1"))
    grid = 0            # 누적 점유 비트마스크
    placed = 0
    occ_area = 0
    for bid, plist in items:
        chosen = None
        if rule == "firstfit":
            for p in plist:                       # 생성순서(배향→x→y) 그대로 첫 적합
                if not (grid & p["fp"]):
                    chosen = p; break
        else:  # blf: 모든 적합 위치 중 (y 최소, x 최소) = 좌하단
            best = None
            for p in plist:
                if grid & p["fp"]:
                    continue
                key = (p["y"], p["x"])
                if best is None or key < best[0]:
                    best = (key, p)
            chosen = best[1] if best else None
        if chosen is not None:
            grid |= chosen["fp"]
            placed += 1
            occ_area += bin(chosen["fp"]).count("1")
    return placed, occ_area


def main():
    path = sys.argv[1]
    bay_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    n_try = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    SX = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    SY = int(sys.argv[5]) if len(sys.argv) > 5 else 1
    THETA = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
    inst = json.load(open(path))
    bay = inst["bays"][bay_idx]
    W, H = bay["width"], bay["height"]
    subset = list(range(min(n_try, len(inst["blocks"]))))
    print(f"=== {inst['name']} bay{bay_idx} ({W}x{H}={W*H}셀) | 블록 {len(subset)}개 시도 "
          f"| 격자 SX={SX} SY={SY} θ={THETA} ===", flush=True)

    t = time.time()
    per_block, Kmax = build_placements(inst, subset, SX, SY, THETA)
    # 해당 베이의 배치만 추림 + footprint 캐시
    bp = []
    for i in subset:
        pl = [p for p in per_block[i] if p["bay"] == bay_idx]
        for p in pl:
            p["fp"] = footprint(p, Kmax)
        if pl:
            bp.append((i, pl))
    print(f"build {time.time()-t:.1f}s, 베이{bay_idx}에 배치가능 블록 {len(bp)}개, Kmax={Kmax}",
          flush=True)

    print(f"\n{'규칙':<28}{'채운블록':>8}{'점유셀':>8}{'밀도(fill%)':>12}")
    print("-" * 56)
    for name, rule, order in [
        ("first-fit (생성순)", "firstfit", "input"),
        ("Bottom-Left (입력순)", "blf", "input"),
        ("Bottom-Left (큰블록먼저)", "blf", "area"),
    ]:
        placed, occ_area = pack(bp, rule, order, W, H)
        fill = 100.0 * occ_area / (W * H)
        print(f"{name:<28}{placed:>8}{occ_area:>8}{fill:>11.1f}%", flush=True)


if __name__ == "__main__":
    main()
