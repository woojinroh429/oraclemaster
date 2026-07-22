#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <cmath>
#include <vector>
namespace py = pybind11;

static const double GEOM_EPS = 1e-9;

static inline double orient(double ax,double ay,double bx,double by,double px,double py){
    return (bx-ax)*(py-ay) - (by-ay)*(px-ax);
}
static inline bool on_seg(double ax,double ay,double bx,double by,double px,double py){
    if(px < std::min(ax,bx)-GEOM_EPS || px > std::max(ax,bx)+GEOM_EPS) return false;
    if(py < std::min(ay,by)-GEOM_EPS || py > std::max(ay,by)+GEOM_EPS) return false;
    return true;
}
static inline bool proper_cross(double ax,double ay,double bx,double by,
                                double cx,double cy,double dx,double dy){
    double d1 = orient(cx,cy,dx,dy,ax,ay);
    double d2 = orient(cx,cy,dx,dy,bx,by);
    double d3 = orient(ax,ay,bx,by,cx,cy);
    double d4 = orient(ax,ay,bx,by,dx,dy);
    if(((d1>GEOM_EPS && d2<-GEOM_EPS)||(d1<-GEOM_EPS && d2>GEOM_EPS)) &&
       ((d3>GEOM_EPS && d4<-GEOM_EPS)||(d3<-GEOM_EPS && d4>GEOM_EPS)))
        return true;
    return false;
}
// poly: pointer to n*2 doubles
static bool point_in_poly_strict(double px,double py,const double* poly,int n){
    for(int i=0;i<n;i++){
        double ax=poly[2*i], ay=poly[2*i+1];
        int ni=(i+1)%n;
        double bx=poly[2*ni], by=poly[2*ni+1];
        double o=orient(ax,ay,bx,by,px,py);
        if(std::fabs(o)<=GEOM_EPS && on_seg(ax,ay,bx,by,px,py)) return false;
    }
    bool inside=false; int j=n-1;
    for(int i=0;i<n;i++){
        double yi=poly[2*i+1], yj=poly[2*j+1];
        double xi=poly[2*i], xj=poly[2*j];
        if((yi>py)!=(yj>py)){
            double xint=(xj-xi)*(py-yi)/(yj-yi)+xi;
            if(px<xint) inside=!inside;
        }
        j=i;
    }
    return inside;
}

// A: (na,2) array, B: (nb,2) array. returns 0/1/2 like numba version
int classify_pair(py::array_t<double,py::array::c_style|py::array::forcecast> A,
                  py::array_t<double,py::array::c_style|py::array::forcecast> B){
    auto ba=A.unchecked<2>(); auto bb=B.unchecked<2>();
    int na=(int)A.shape(0), nb=(int)B.shape(0);
    if(na<3||nb<3) return 2;
    const double* pa=A.data(); const double* pb=B.data();
    double axmin=pa[0],axmax=pa[0],aymin=pa[1],aymax=pa[1];
    for(int i=1;i<na;i++){
        double x=pa[2*i],y=pa[2*i+1];
        if(x<axmin)axmin=x; if(x>axmax)axmax=x;
        if(y<aymin)aymin=y; if(y>aymax)aymax=y;
    }
    double bxmin=pb[0],bxmax=pb[0],bymin=pb[1],bymax=pb[1];
    for(int i=1;i<nb;i++){
        double x=pb[2*i],y=pb[2*i+1];
        if(x<bxmin)bxmin=x; if(x>bxmax)bxmax=x;
        if(y<bymin)bymin=y; if(y>bymax)bymax=y;
    }
    if(!(axmin<bxmax && bxmin<axmax && aymin<bymax && bymin<aymax)) return 2;
    for(int i=0;i<na;i++){
        double ax=pa[2*i],ay=pa[2*i+1]; int ni=(i+1)%na;
        double bx2=pa[2*ni],by2=pa[2*ni+1];
        for(int k=0;k<nb;k++){
            double cx=pb[2*k],cy=pb[2*k+1]; int nk=(k+1)%nb;
            double dx=pb[2*nk],dy=pb[2*nk+1];
            if(proper_cross(ax,ay,bx2,by2,cx,cy,dx,dy)) return 1;
        }
    }
    for(int i=0;i<na;i++) if(point_in_poly_strict(pa[2*i],pa[2*i+1],pb,nb)) return 1;
    for(int k=0;k<nb;k++) if(point_in_poly_strict(pb[2*k],pb[2*k+1],pa,na)) return 1;
    return 0;
}


py::array_t<int> classify_batch(
    py::array_t<double,py::array::c_style|py::array::forcecast> newp,
    py::array_t<double,py::array::c_style|py::array::forcecast> flat,
    py::array_t<int,py::array::c_style|py::array::forcecast> offsets)
{
    const double* np_ = newp.data();
    int nn = (int)newp.shape(0);
    const double* fl = flat.data();
    auto off = offsets.unchecked<1>();
    int ncount = (int)offsets.shape(0) - 1;
    auto result = py::array_t<int>(ncount);
    int* res = result.mutable_data();
    for(int q=0;q<ncount;q++){
        int s=off(q), e=off(q+1); int nb=e-s;
        const double* bp = fl + 2*s;
        if(nn<3||nb<3){ res[q]=2; continue; }
        double axmin=np_[0],axmax=np_[0],aymin=np_[1],aymax=np_[1];
        for(int i=1;i<nn;i++){double x=np_[2*i],y=np_[2*i+1];
            if(x<axmin)axmin=x; if(x>axmax)axmax=x; if(y<aymin)aymin=y; if(y>aymax)aymax=y;}
        double bxmin=bp[0],bxmax=bp[0],bymin=bp[1],bymax=bp[1];
        for(int i=1;i<nb;i++){double x=bp[2*i],y=bp[2*i+1];
            if(x<bxmin)bxmin=x; if(x>bxmax)bxmax=x; if(y<bymin)bymin=y; if(y>bymax)bymax=y;}
        if(!(axmin<bxmax && bxmin<axmax && aymin<bymax && bymin<aymax)){ res[q]=2; continue; }
        int r=0; bool done=false;
        for(int i=0;i<nn && !done;i++){
            double ax=np_[2*i],ay=np_[2*i+1]; int ni=(i+1)%nn;
            double bx2=np_[2*ni],by2=np_[2*ni+1];
            for(int k=0;k<nb;k++){
                double cx=bp[2*k],cy=bp[2*k+1]; int nk=(k+1)%nb;
                double dx=bp[2*nk],dy=bp[2*nk+1];
                if(proper_cross(ax,ay,bx2,by2,cx,cy,dx,dy)){ r=1;done=true;break; }
            }
        }
        if(!done) for(int i=0;i<nn;i++) if(point_in_poly_strict(np_[2*i],np_[2*i+1],bp,nb)){r=1;done=true;break;}
        if(!done) for(int k=0;k<nb;k++) if(point_in_poly_strict(bp[2*k],bp[2*k+1],np_,nn)){r=1;done=true;break;}
        res[q]=r;
    }
    return result;
}


// 두 블록의 레이어집합 비교. A_flat/A_off: 새블록 레이어들, B_flat/B_off: 기존블록 레이어들.
// k는 A레이어 인덱스, j는 B레이어. j>=k_min[k] 만 검사 (기존 j>=k 규칙).
// 반환: [status, k1,j1, k2,j2, ...] status=1이면 첫쌍(k1,j1)이 겹침(c==1).
//   status=0이면 겹침없음, 뒤에 애매(c==0) 쌍들의 (k,j) 나열.
py::array_t<int> classify_blockpair(
    py::array_t<double,py::array::c_style|py::array::forcecast> Af,
    py::array_t<int,py::array::c_style|py::array::forcecast> Ao,
    py::array_t<double,py::array::c_style|py::array::forcecast> Bf,
    py::array_t<int,py::array::c_style|py::array::forcecast> Bo,
    int same_block)
{
    const double* af=Af.data(); const double* bf=Bf.data();
    auto ao=Ao.unchecked<1>(); auto bo=Bo.unchecked<1>();
    int na_layers=(int)Ao.shape(0)-1;
    int nb_layers=(int)Bo.shape(0)-1;
    std::vector<int> amb;
    for(int k=0;k<na_layers;k++){
        int as=ao(k), ae=ao(k+1); int nn=ae-as;
        if(nn<3) continue;
        const double* A=af+2*as;
        // same_block이면 j>=k, 아니면 j는 0부터 (다른 블록끼리는 모든 레이어쌍)
        int jstart = same_block ? k : 0;
        for(int j=jstart;j<nb_layers;j++){
            int bs=bo(j), be=bo(j+1); int nb=be-bs;
            if(nb<3) continue;
            const double* B=bf+2*bs;
            // inline classify (A vs B)
            double axmin=A[0],axmax=A[0],aymin=A[1],aymax=A[1];
            for(int i=1;i<nn;i++){double x=A[2*i],y=A[2*i+1];
                if(x<axmin)axmin=x; if(x>axmax)axmax=x; if(y<aymin)aymin=y; if(y>aymax)aymax=y;}
            double bxmin=B[0],bxmax=B[0],bymin=B[1],bymax=B[1];
            for(int i=1;i<nb;i++){double x=B[2*i],y=B[2*i+1];
                if(x<bxmin)bxmin=x; if(x>bxmax)bxmax=x; if(y<bymin)bymin=y; if(y>bymax)bymax=y;}
            if(!(axmin<bxmax && bxmin<axmax && aymin<bymax && bymin<aymax)) continue;
            int c=0; bool done=false;
            for(int i=0;i<nn && !done;i++){
                double ax=A[2*i],ay=A[2*i+1]; int ni=(i+1)%nn;
                double bx2=A[2*ni],by2=A[2*ni+1];
                for(int kk=0;kk<nb;kk++){
                    double cx=B[2*kk],cy=B[2*kk+1]; int nk=(kk+1)%nb;
                    double dx=B[2*nk],dy=B[2*nk+1];
                    if(proper_cross(ax,ay,bx2,by2,cx,cy,dx,dy)){c=1;done=true;break;}
                }
            }
            if(!done){for(int i=0;i<nn;i++) if(point_in_poly_strict(A[2*i],A[2*i+1],B,nb)){c=1;done=true;break;}}
            if(!done){for(int kk=0;kk<nb;kk++) if(point_in_poly_strict(B[2*kk],B[2*kk+1],A,nn)){c=1;done=true;break;}}
            if(c==1){
                auto r=py::array_t<int>(3); int* rp=r.mutable_data();
                rp[0]=1; rp[1]=k; rp[2]=j; return r;
            }
            if(c==0){ amb.push_back(k); amb.push_back(j); }
        }
    }
    auto r=py::array_t<int>(1+(int)amb.size()); int* rp=r.mutable_data();
    rp[0]=0;
    for(size_t i=0;i<amb.size();i++) rp[1+i]=amb[i];
    return r;
}

PYBIND11_MODULE(ogc_geom, m){
    m.def("classify_pair", &classify_pair);
    m.def("classify_batch", &classify_batch);
    m.def("classify_blockpair", &classify_blockpair);
}
