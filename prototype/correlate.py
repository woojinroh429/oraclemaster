# 배치방향 승자/이득과 인스턴스 특징의 상관분석.
import numpy as np
# inst: bl_z1, cp_z1(coreperi), bestother_z1, dens, acv, capcv, aspmx, aspmean, m, n, bigfrac, amaxmn
D = {
 21:(51,  54,  51,  0.78,0.59,0.27,9.7, 6.4,3,100,0.58,2.7),
 23:(193, 157, 157, 0.86,0.63,0.37,6.5, 4.5,2,100,0.60,2.9),
 25:(366, 367, 348, 1.29,0.69,0.44,5.2, 3.8,2,100,0.63,3.0),
 26:(605, 571, 571, 1.00,0.49,0.23,10.5,7.2,3,150,0.54,2.3),
 27:(1564,1745,1564,1.63,0.64,0.44,10.5,6.5,2,150,0.60,2.9),
 30:(208, 216, 208, 0.90,0.68,0.45,6.5, 4.8,2,150,0.61,3.1),
 31:(332, 343, 320, 0.90,0.70,0.42,7.3, 4.8,4,200,0.64,3.0),
 32:(353, 306, 306, 0.86,0.61,0.40,10.6,6.5,3,200,0.58,3.2),
 33:(981, 810, 810, 1.14,0.52,0.19,7.8, 5.9,3,200,0.56,2.5),
 35:(51,  66,  51,  0.83,0.74,0.49,5.9, 4.4,3,200,0.65,3.1),
 37:(487, 477, 477, 0.96,0.62,0.40,7.1, 6.5,3,250,0.59,3.1),
 38:(2359,2445,2359,1.57,0.66,0.36,4.3, 4.2,3,250,0.61,2.9),
 39:(490, 611, 490, 0.98,0.55,0.21,6.9, 5.6,3,250,0.56,2.6),
 40:(2416,2504,2416,1.33,0.54,0.26,7.8, 5.9,4,250,0.56,2.5),
}
names=["dens","acv","capcv","aspmx","aspmean","m","n","bigfrac","amaxmn"]
rows=[]
bestgain=[]; cpgain=[]; feat={k:[] for k in names}
for inst,v in D.items():
    bl,cp,bo=v[0],v[1],v[2]
    bg=(bl-bo)/bl*100      # best-of 이득%
    cg=(bl-cp)/bl*100      # coreperi 이득%
    bestgain.append(bg); cpgain.append(cg)
    for i,k in enumerate(names): feat[k].append(v[3+i])
bestgain=np.array(bestgain); cpgain=np.array(cpgain)
def pear(x,y):
    x=np.array(x,float); y=np.array(y,float)
    if x.std()==0 or y.std()==0: return 0.0
    return np.corrcoef(x,y)[0,1]
print("=== Pearson 상관계수 (특징 vs 이득%) ===")
print(f"{'특징':<9} {'best-of이득':>10} {'coreperi이득':>12}")
for k in names:
    print(f"{k:<9} {pear(feat[k],bestgain):>10.2f} {pear(feat[k],cpgain):>12.2f}")
print()
# 밀도 구간별 평균 이득
print("=== 밀도구간별 best-of 이득 ===")
dens=np.array(feat["dens"])
for lo,hi,lab in [(0,0.85,'저(<0.85)'),(0.85,1.15,'중(0.85~1.15)'),(1.15,9,'고(>1.15)')]:
    mask=(dens>=lo)&(dens<hi)
    if mask.sum(): print(f"  {lab:<16} n={mask.sum()} 평균이득={bestgain[mask].mean():.1f}% 최대={bestgain[mask].max():.1f}%")
