"""Numba 가속 pricing 커널: 감축비용 rc = cost - pi - Σμ(cells) 를 블록의 모든
(배치 × EN)에 대해 일괄 계산. 마스크는 uint64 워드, μ는 dense 배열."""
import numpy as np
from numba import njit


def to_words(m, WORDS):
    """python 큰정수 비트마스크 → uint64 워드 배열."""
    a = np.zeros(WORDS, np.uint64)
    for w in range(WORDS):
        a[w] = np.uint64(m & 0xFFFFFFFFFFFFFFFF)
        m >>= 64
    return a


def pack_block(placements, Kmax, WORDS):
    """블록의 placement 리스트 → (occ_w, shd_w, bay, prefloss) numpy 배열."""
    n = len(placements)
    occ_w = np.zeros((n, Kmax, WORDS), np.uint64)
    shd_w = np.zeros((n, Kmax, WORDS), np.uint64)
    bay = np.zeros(n, np.int32)
    prefloss = np.zeros(n, np.float64)
    for k, p in enumerate(placements):
        bay[k] = p["bay"]
        prefloss[k] = p["prefloss"]
        for L in range(1, Kmax + 1):
            occ_w[k, L - 1] = to_words(p["occ"][L], WORDS)
            shd_w[k, L - 1] = to_words(p["shadow"][L], WORDS)
    return occ_w, shd_w, bay, prefloss


@njit(cache=True, fastmath=True)
def price_block(occ_w, shd_w, bay, prefloss, en_arr, P, due, w1, w3, pi, mu_arr):
    """rc[p, e] = cost - pi - Σ_{cell∈occ+} mu.  mu_arr[bay, L, day, cell]."""
    nplace = occ_w.shape[0]
    Kmax = occ_w.shape[1]
    WORDS = occ_w.shape[2]
    nen = en_arr.shape[0]
    rc = np.empty((nplace, nen), np.float64)
    for p in range(nplace):
        b = bay[p]
        for e in range(nen):
            EN = en_arr[e]
            EX = EN + P
            tard = EX - due
            if tard < 0:
                tard = 0
            cost = w1 * tard + w3 * prefloss[p]
            smu = 0.0
            for day in range(EN, EX):
                boundary = (day == EN) or (day == EX - 1)
                for L in range(Kmax):
                    for w in range(WORDS):
                        bits = shd_w[p, L, w] if boundary else occ_w[p, L, w]
                        if bits == 0:
                            continue
                        base = w * 64
                        while bits:
                            low = bits & (~bits + np.uint64(1))   # 최하위 셋비트
                            idx = base + int(np.log2(np.float64(low)))
                            smu += mu_arr[b, L, day, idx]
                            bits ^= low
            rc[p, e] = cost - pi - smu
    return rc
