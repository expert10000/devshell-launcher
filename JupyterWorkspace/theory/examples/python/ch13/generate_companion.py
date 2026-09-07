from pathlib import Path
import json, numpy as np, matplotlib.pyplot as plt
from electrostatics import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch13/computational'; OUT.mkdir(parents=True,exist_ok=True)
def save(name): plt.tight_layout(); plt.savefig(OUT/name); plt.close()
# grids
x=np.linspace(-3,3,241); X,Y=np.meshgrid(x,x); P=np.stack([X,Y],axis=-1)
V=point_potential(P,[1,-1],[[-.8,0],[.8,0]],.06); E=point_field(P,[1,-1],[[-.8,0],[.8,0]],.08)
plt.figure(figsize=(6,5)); plt.contour(X,Y,V,levels=np.linspace(-2,2,17)); plt.streamplot(x,x,E[...,0],E[...,1],density=1.1); plt.scatter([-.8,.8],[0,0]); save('dipole_potential_field.pdf')
V3=point_potential(P,[1,1,-1.4],[[-1,0],[1,0],[0,1.2]],.08)
plt.figure(figsize=(6,5)); plt.contourf(X,Y,np.clip(V3,-3,3),levels=31); plt.colorbar(label='V'); save('three_charge_potential.pdf')
z=np.linspace(0,4,160); plt.figure(figsize=(6,4)); plt.plot(z,ring_axis_exact(z),label='analytic'); plt.plot(z,ring_axis_potential(z,n=64),'--',label='64 elements'); plt.legend(); plt.xlabel('z/a'); plt.ylabel('V/(kQ/a)'); save('ring_axis_validation.pdf')
r=np.logspace(.2,1.5,100); pts=np.c_[r*np.cos(.55),r*np.sin(.55)]; err=np.abs((dipole_approx(pts)-dipole_exact(pts))/dipole_exact(pts)); plt.figure(figsize=(6,4)); plt.loglog(r,err,label='measured'); plt.loglog(r,0.03/r**2,'--',label=r'$r^{-2}$ guide'); plt.legend(); plt.xlabel('r/d'); plt.ylabel('relative error'); save('multipole_error.pdf')
n=101; xx=np.linspace(-1,1,n); h=xx[1]-xx[0]; XX,YY=np.meshgrid(xx,xx); rho=180*np.exp(-((XX+.35)**2+YY**2)/.035)-180*np.exp(-((XX-.35)**2+YY**2)/.035); v,hist=solve_poisson(rho,h,tol=2e-5)
plt.figure(figsize=(6,5)); plt.contourf(XX,YY,v,31); plt.colorbar(label='V'); save('poisson_solution.pdf')
plt.figure(figsize=(6,4)); plt.semilogy(np.arange(len(hist))*20,hist); plt.xlabel('iteration'); plt.ylabel('max residual'); save('poisson_residual.pdf')
ns=np.array([41,61,81,121,161]); errs=[]; energies=[]
for nn in ns:
    a=np.linspace(-2,2,nn); hh=a[1]-a[0]; A,B=np.meshgrid(a,a); PP=np.stack([A,B],axis=-1); vv=point_potential(PP,[1],[[(0,0)]],.25); ex,ey=gradient_field(vv,hh); ee=point_field(PP,[1],[[0,0]],.25); mask=A*A+B*B>.5**2; errs.append(np.sqrt(np.mean((ex[mask]-ee[...,0][mask])**2+(ey[mask]-ee[...,1][mask])**2))); energies.append(field_energy(ex,ey,hh))
plt.figure(figsize=(6,4)); plt.loglog(4/(ns-1),errs,'o-'); plt.loglog(4/(ns-1),errs[-1]*(4/(ns-1)/(4/(ns[-1]-1)))**2,'--'); plt.xlabel('h'); plt.ylabel('RMS field error'); save('gradient_convergence.pdf')
plt.figure(figsize=(6,4)); plt.plot(ns,energies,'o-'); plt.xlabel('grid points per axis'); plt.ylabel('discrete field energy'); save('energy_convergence.pdf')
summary={'ring_max_error_64':float(np.max(np.abs(ring_axis_potential(z,n=64)-ring_axis_exact(z)))),'poisson_final_residual':float(hist[-1]),'gradient_errors':list(map(float,errs)),'energies':list(map(float,energies))}
(OUT/'companion_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
