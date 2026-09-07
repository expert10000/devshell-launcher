from pathlib import Path
import json, sys
import numpy as np
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'generated/ch14/computational'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(HERE))
from bounded_electrostatics import *

plt.rcParams.update({'figure.figsize':(6.4,4.2),'font.size':10,'savefig.bbox':'tight'})

def save(name):
    plt.savefig(OUT/name)
    plt.close()

# 1. Capacitance matrix
p=np.array([[0,2.0,.7],[2.0,0,1.1],[.7,1.1,0]])
c=nodal_capacitance(p,np.array([1.0,1.5,2.0]))
plt.imshow(c); plt.colorbar(label='capacitance coefficient')
plt.xticks(range(3),['1','2','3']); plt.yticks(range(3),['1','2','3'])
plt.title('Symmetric nodal capacitance matrix')
for i in range(3):
    for j in range(3): plt.text(j,i,f'{c[i,j]:.1f}',ha='center',va='center')
save('capacitance_matrix.pdf')

# 2. Guard response
ratios=np.logspace(-2,2,200); response=ratios/(1+ratios)
plt.semilogx(ratios,response); plt.xlabel(r'$C_{sg}/C_{s0}$'); plt.ylabel(r'$V_s/V_g$')
plt.grid(True); plt.title('Floating-node response to a driven guard')
save('floating_guard_response.pdf')

# 3. Layered dielectric potential
z=np.linspace(0,1,400); v=layered_potential(z,[.35,.65],[2,6],1)
plt.plot(z,v); plt.axvline(.35,ls='--'); plt.xlabel('normalized depth'); plt.ylabel('potential')
plt.title('Piecewise-linear potential in layered dielectrics'); plt.grid(True)
save('layered_dielectric_potential.pdf')

# 4. Grounded plane image solution
x=np.linspace(-3,3,260); zz=np.linspace(.03,3,220); X,Z=np.meshgrid(x,zz)
V=image_plane_potential(X,Z,height=1)
levels=np.r_[-2,-1,-.5,-.2,.2,.5,1,2]
plt.contour(X,Z,np.clip(V,-2.5,2.5),levels=levels)
plt.axhline(0,lw=2); plt.scatter([0],[1],s=25); plt.xlabel('x'); plt.ylabel('z')
plt.title('Image-charge solution above a grounded plane')
save('image_plane_contours.pdf')

# 5. Grounded sphere boundary validation
th=np.linspace(0,np.pi,400); vb=image_sphere_potential(np.ones_like(th),th,a=1,d=2.2)
plt.plot(th,vb); plt.xlabel(r'$\theta$'); plt.ylabel(r'$V(a,\theta)$')
plt.title('Grounded-sphere boundary residual'); plt.grid(True)
save('image_sphere_boundary.pdf')

# 6. Rectangle modal decay
y=np.linspace(0,1,300)
for n in [1,2,4,8]:
    amp=np.sinh(n*np.pi*y)/np.sinh(n*np.pi)
    plt.semilogy(1-y,np.maximum(amp,1e-12),label=f'n={n}')
plt.xlabel('distance below driven boundary'); plt.ylabel('mode amplitude'); plt.legend(); plt.grid(True)
plt.title('High-spatial-frequency boundary modes decay fastest')
save('rectangle_mode_decay.pdf')

# 7. Numerical Laplace solution and residual
n=81; h=1/(n-1); xx=np.linspace(0,1,n)
b=np.full((n,n),np.nan); b[0,:]=0; b[-1,:]=np.sin(np.pi*xx)+.35*np.sin(4*np.pi*xx); b[:,0]=0; b[:,-1]=0
sol,hist=solve_laplace_dirichlet(b,h,tol=5e-8)
plt.imshow(sol,origin='lower',extent=[0,1,0,1],aspect='auto'); plt.colorbar(label='V')
plt.xlabel('x'); plt.ylabel('y'); plt.title('Finite-difference Dirichlet solution')
save('laplace_solution.pdf')
plt.semilogy(10*np.arange(len(hist)),hist); plt.xlabel('SOR iteration'); plt.ylabel('maximum residual')
plt.grid(True); plt.title('Residual-based convergence diagnostic')
save('laplace_residual.pdf')

# 8. Pull-in equilibrium curve
u=np.linspace(0,.94,500); drive=2*u*(1-u)**2
plt.plot(u,drive); plt.axvline(1/3,ls='--'); plt.xlabel(r'$x/g$'); plt.ylabel('normalized voltage squared')
plt.title('Static actuator branch and pull-in point'); plt.grid(True)
save('pull_in_curve.pdf')

summary={
 'figures':9,
 'tests':14,
 'capacitance_matrix_symmetry_error':float(np.max(np.abs(c-c.T))),
 'grounded_sphere_boundary_error':float(np.max(np.abs(vb))),
 'laplace_final_residual':float(hist[-1]),
 'pull_in_displacement_ratio':1/3,
}
(OUT/'companion_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
