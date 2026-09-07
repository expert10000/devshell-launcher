from __future__ import annotations
import json, math
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'generated/ch15/computational'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(HERE))
from magnetostatics_companion import *


def save(name):
    plt.tight_layout(); plt.savefig(OUT/name,bbox_inches='tight'); plt.close()

# 1 loop field and dipole
z=np.linspace(0,6,400); exact=loop_axis_field(z,1,1); b0=loop_axis_field(0,1,1)
plt.figure(figsize=(6.2,3.6)); plt.plot(z,exact/b0,label='exact loop')
zd=np.linspace(.8,6,350); plt.plot(zd,dipole_axis_field(zd,math.pi)/b0,'--',label='dipole')
plt.xlabel(r'$z/a$');plt.ylabel(r'$B_z/B_z(0)$');plt.ylim(0,1.05);plt.legend();plt.grid(alpha=.25);save('loop_axis_field.pdf')

# 2 finite solenoid
z=np.linspace(-1.2,1.2,500); vals=solenoid_axis_field(z,.18,1.4,700,1)
plt.figure(figsize=(6.2,3.6));plt.plot(z,vals/(MU0*(700/1.4)))
plt.axvline(-.7,ls=':');plt.axvline(.7,ls=':');plt.xlabel(r'$z$');plt.ylabel(r'$B_z/(\mu_0 nI)$');plt.grid(alpha=.25);save('solenoid_axis_field.pdf')

# 3 gauge curl errors
x=np.linspace(-1,1,51);xx,yy=np.meshgrid(x,x);h=x[1]-x[0];B=.8
errs=[]
for fn in (symmetric_gauge,landau_gauge):
    ax,ay=fn(xx,yy,B);errs.append(np.max(abs(curl_z(ax,ay,h)-B),axis=0))
plt.figure(figsize=(6.2,3.6));plt.semilogy(x,np.maximum(errs[0],1e-17),label='symmetric gauge');plt.semilogy(x,np.maximum(errs[1],1e-17),'--',label='Landau gauge')
plt.xlabel(r'$x$');plt.ylabel('maximum curl error');plt.legend();plt.grid(alpha=.25);save('gauge_curl_error.pdf')

# 4 far field error
z=np.logspace(.05,2,350); rel=abs(loop_axis_field(z,1,1)/dipole_axis_field(z,math.pi)-1)
plt.figure(figsize=(6.2,3.6));plt.loglog(z,rel);plt.xlabel(r'$z/a$');plt.ylabel('relative dipole error');plt.grid(alpha=.25,which='both');save('dipole_farfield_error.pdf')

# 5 demag response
chi=np.logspace(-2,4,400);plt.figure(figsize=(6.2,3.6))
for N,label in [(0,'closed path $N=0$'),(1/3,'sphere $N=1/3$'),(1,'thin plate $N=1$')]:plt.loglog(chi,apparent_susceptibility(chi,N),label=label)
plt.xlabel(r'intrinsic $\chi_m$');plt.ylabel(r'apparent $\chi_{\rm app}$');plt.legend();plt.grid(alpha=.25,which='both');save('demag_response.pdf')

# 6 hysteresis
hup=np.linspace(-500,500,1000);hdown=hup[::-1];bup,_=hysteresis_branches(hup);_,bdown=hysteresis_branches(hdown)
plt.figure(figsize=(5.2,4));plt.plot(hup,bup);plt.plot(hdown,bdown);plt.xlabel(r'$H$ (A/m)');plt.ylabel(r'$B$ (T)');plt.grid(alpha=.25);save('hysteresis_surrogate.pdf')

# 7 gap flux
g=np.linspace(0,2e-3,400);b=gapped_core_flux_density(.5,500,.25,1500,g)
plt.figure(figsize=(6.2,3.6));plt.plot(g*1e3,b);plt.xlabel('gap (mm)');plt.ylabel(r'$B$ (T)');plt.grid(alpha=.25);save('core_gap_flux.pdf')

# 8 localized current FD
n=81;axis=np.linspace(0,1,n);xx,yy=np.meshgrid(axis,axis);J=np.exp(-((xx-.5)**2+(yy-.5)**2)/.012)
source=-J  # normalized equation laplacian(A)=-J
res=solve_poisson_dirichlet(source,tolerance=2e-7,max_iterations=40000)
az=res.potential; bx=np.gradient(az,res.spacing,axis=0);by=-np.gradient(az,res.spacing,axis=1)
plt.figure(figsize=(5.4,4.5));plt.contourf(xx,yy,az,25);skip=5;plt.quiver(xx[::skip,::skip],yy[::skip,::skip],bx[::skip,::skip],by[::skip,::skip],scale=8)
plt.xlabel('$x$');plt.ylabel('$y$');plt.colorbar(label='$A_z$');save('vector_potential_fd.pdf')

# 9 convergence
sizes=[21,31,41,61];errs2=[];hs=[];hist=None
for n in sizes:
    exact,src,_=manufactured_solution(n);r=solve_poisson_dirichlet(src,tolerance=2e-7,max_iterations=40000);errs2.append(max_error(r.potential,exact));hs.append(r.spacing)
    if n==41:hist=r.residual_history
fig=plt.figure(figsize=(6.3,3.8));ax=fig.add_subplot(111);ax.loglog(hs,errs2,'o-',label='max solution error');ax.loglog(hs,[errs2[-1]*(h/hs[-1])**2 for h in hs],'--',label='$O(h^2)$ reference');ax.set_xlabel('$h$');ax.set_ylabel('error');ax.grid(alpha=.25,which='both');ax.legend();save('fd_convergence.pdf')

summary={
 'figure_count':9,
 'loop_center_relative_error':float(abs(loop_axis_field(0,1,1)/(MU0/2)-1)),
 'gauge_curl_max_error':float(max(np.max(errs[0]),np.max(errs[1]))),
 'dipole_relative_error_at_20a':float(abs(loop_axis_field(20,1,1)/dipole_axis_field(20,math.pi)-1)),
 'sphere_apparent_chi_at_1e4':float(apparent_susceptibility(1e4,1/3)),
 'hysteresis_loop_area_J_per_m3':hysteresis_loop_area(),
 'fd_final_residual':float(res.residual_history[-1]),
 'manufactured_errors':dict(zip(map(str,sizes),map(float,errs2))),
}
(OUT/'companion_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
