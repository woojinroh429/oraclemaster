import time, numpy as np
from numba import njit

# pricing 핫루프 모사: K개 후보 배치가 각각 시공간 셀 마스크를 가지고,
# 쌍대(dual) 벡터와의 Σ(set bit ∩ dual) 를 계산 (감축비용의 -Σμ 항).
NCELL = 4000          # 시공간 셀 수 (bay×layer×day×bit 일부)
WORDS = (NCELL+63)//64
K = 20000             # 후보 배치 수 (블록×위치×EN 규모)
rng = np.random.default_rng(0)
dual = rng.random(NCELL).astype(np.float64) * -1.0     # μ<=0
# 각 후보: 무작위 60개 셀 점유 (발자국×일수 규모)
masks_words = np.zeros((K, WORDS), dtype=np.uint64)
cells_list = []
for k in range(K):
    cells = rng.choice(NCELL, 60, replace=False)
    cells_list.append(set(int(c) for c in cells))
    for c in cells:
        masks_words[k, c//64] |= np.uint64(1) << np.uint64(c%64)

# ---- 순수 파이썬 (dict/set 스캔) ----
dual_py = {i: float(dual[i]) for i in range(NCELL)}
t=time.time()
acc=0.0
for k in range(K):
    s=0.0
    for c in cells_list[k]:
        s += dual_py[c]
    acc += s
py_t=time.time()-t
print(f"pure python : {py_t*1000:8.1f} ms   (acc={acc:.1f})")

# ---- Numba njit (uint64 워드 + 비트순회) ----
@njit(cache=True, fastmath=True)
def price_all(masks, dual, words):
    K=masks.shape[0]; out=0.0
    for k in range(K):
        s=0.0
        for w in range(words):
            bits=masks[k,w]
            base=w*64
            while bits:
                b=bits & (~bits+np.uint64(1))     # lowest set bit
                idx=base + int(np.log2(np.float64(b)))
                s += dual[idx]
                bits ^= b
        out+=s
    return out
_=price_all(masks_words[:10], dual, WORDS)  # warmup(compile)
t=time.time()
acc2=price_all(masks_words, dual, WORDS)
nb_t=time.time()-t
print(f"numba njit  : {nb_t*1000:8.1f} ms   (acc={acc2:.1f})")
print(f"speedup     : {py_t/nb_t:6.1f}x")
