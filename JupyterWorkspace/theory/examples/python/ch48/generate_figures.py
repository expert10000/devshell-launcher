from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from quantum_geometry_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch48/computational'; OUT.mkdir(parents=True,exist_ok=True)
for p in OUT.glob('*.pdf'): p.unlink()
def save(name):
    plt.tight_layout(); plt.savefig(OUT/name); plt.close()

# 1 two-level metric-curvature saturation
k=np.linspace(0,3,350); det=[]; cur=[]
for x in k:
    gx,gy,gxy,f=two_level_lower_geometry(float(x),0.0,1.0); det.append(np.sqrt(metric_determinant(gx,gy,gxy))); cur.append(abs(f)/2)
plt.figure(figsize=(4.6,3)); plt.plot(k,det,label='sqrt(det g)'); plt.plot(k,cur,'--',label='|F|/2'); plt.xlabel('k / mass scale'); plt.ylabel('geometric density'); plt.title('Two-level determinant saturation'); plt.legend(); save('01_two_level_metric_curvature.pdf')

# 2 integrated metric topological lower bound
C=np.arange(0,5); b=np.array([integrated_metric_lower_bound(int(c)) for c in C]); plt.figure(figsize=(4.6,3)); plt.plot(C,b,'o-'); plt.xlabel('|C|'); plt.ylabel('minimum integral tr g'); plt.title('Integrated metric cost of topology'); save('02_integrated_metric_bound.pdf')

# 3 Landau form factors
q=np.linspace(0,4,450); plt.figure(figsize=(4.6,3));
for n in range(3): plt.plot(q,landau_form_factor(n,q),label=f'n={n}')
plt.xlabel('q l_B'); plt.ylabel('F_n(q)'); plt.title('Landau-level form factors'); plt.legend(); save('03_landau_form_factors.pdf')

# 4 GMP sine structure
area=np.linspace(-2*np.pi,2*np.pi,500); coeff=2*np.sin(area/2); plt.figure(figsize=(4.6,3)); plt.plot(area,coeff); plt.xlabel('l_B^2 (q x qprime)'); plt.ylabel('GMP sine coefficient'); plt.title('Projected-density noncommutativity'); save('04_gmp_structure.pdf')

# 5 geometric fluctuation quality
amp=np.linspace(0,0.8,100); cfl=[]; mfl=[]
theta=np.linspace(0,2*np.pi,600,endpoint=False)
for a in amp:
    curvature=1+a*np.cos(theta); metric=2+0.7*a*np.sin(theta); x,y=geometry_quality(curvature,metric); cfl.append(x); mfl.append(y)
plt.figure(figsize=(4.6,3)); plt.plot(amp,cfl,label='curvature RMS/mean'); plt.plot(amp,mfl,label='metric RMS/mean'); plt.xlabel('synthetic modulation amplitude'); plt.ylabel('normalized fluctuation'); plt.title('Chern-band geometric uniformity'); plt.legend(); save('05_geometry_fluctuation_quality.pdf')

# 6 projected-band hierarchy
U=np.logspace(-1,2,350); W=0.5; Delta=100.; plt.figure(figsize=(4.6,3)); plt.loglog(U,W/U,label='W/U'); plt.loglog(U,U/Delta,label='U/Delta'); plt.axhline(.2,linestyle=':'); plt.xlabel('interaction scale U'); plt.ylabel('dimensionless ratio'); plt.title('Projection hierarchy window'); plt.legend(); save('06_projection_hierarchy.pdf')

# 7 fractional response from topological multiplets
d=np.arange(1,8); r=np.array([fractional_hall_response(1,int(x)) for x in d]); plt.figure(figsize=(4.6,3)); plt.plot(d,r,'o-'); plt.xlabel('ground-state manifold size'); plt.ylabel('sigma_xy / (e^2/h) for total C=1'); plt.title('Fractional response of a Chern multiplet'); save('07_fractional_multiplet_response.pdf')

# 8 Hall viscosity and shift
shift=np.arange(1,8); eta=np.array([hall_viscosity(1,float(s)) for s in shift]); plt.figure(figsize=(4.6,3)); plt.plot(shift,eta,'o-'); plt.xlabel('shift S'); plt.ylabel('eta_H / (hbar rho)'); plt.title('Hall viscosity in the isotropic continuum'); save('08_hall_viscosity_shift.pdf')

# 9 structure-factor q4 lower-bound curves
q=np.linspace(0,.9,350); plt.figure(figsize=(4.6,3));
for S in (1,3,5):
    s4=structure_factor_s4_bound(S); plt.plot(q,projected_structure_factor_leading(q,s4),label=f'S={S}, s4 bound={s4:.2f}')
plt.xlabel('q l_B'); plt.ylabel('leading Sbar(q)'); plt.title('Guiding-center q^4 geometric bound'); plt.legend(); save('09_structure_factor_bounds.pdf')
print('generated',len(list(OUT.glob('*.pdf'))),'figures in',OUT)
