from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from anyons_tqc_companion import *
OUT=Path(__file__).resolve().parents[3]/'generated/ch47/computational'; OUT.mkdir(parents=True,exist_ok=True)
for p in OUT.glob('*.pdf'): p.unlink()
def save(name):
    plt.tight_layout(); plt.savefig(OUT/name); plt.close()
# 1 fusion-space growth
N=np.arange(1,16); dims=np.array([sum(fibonacci_fusion_dimensions(int(n))) for n in N]); plt.figure(figsize=(4.6,3)); plt.semilogy(N,dims,'o-'); plt.xlabel('number of tau anyons'); plt.ylabel('total fusion paths'); plt.title('Fibonacci fusion-space growth'); save('01_fibonacci_fusion_growth.pdf')
# 2 braid-generator eigenphases
b1,b2=fibonacci_braid_generators(); th1=np.angle(np.linalg.eigvals(b1)); th2=np.angle(np.linalg.eigvals(b2)); plt.figure(figsize=(4.6,3)); x=np.arange(2); plt.scatter(np.cos(th1),np.sin(th1),label='B1'); plt.scatter(np.cos(th2),np.sin(th2),marker='x',label='B2'); t=np.linspace(0,2*np.pi,300); plt.plot(np.cos(t),np.sin(t),linewidth=.8); plt.axis('equal'); plt.xlabel('Re eigenvalue'); plt.ylabel('Im eigenvalue'); plt.title('Fibonacci braid spectra'); plt.legend(); save('02_fibonacci_braid_spectrum.pdf')
# 3 braid relation residual under rounded matrices
prec=np.arange(2,15); res=[]
for n in prec:
    a,b=fibonacci_braid_generators(); a=np.round(a,n); b=np.round(b,n); res.append(braid_relation_residual(a,b))
plt.figure(figsize=(4.6,3)); plt.semilogy(prec,np.maximum(res,1e-18),'o-'); plt.xlabel('decimal precision retained'); plt.ylabel('braid-relation residual'); plt.title('Braid consistency under numerical precision'); save('03_braid_relation_residual.pdf')
# 4 compilation convergence for Hadamard target
H=np.array([[1,1],[1,-1]],complex)/np.sqrt(2); depth=np.arange(0,10); err=np.array([best_braid_approximation(H,int(d))[0] for d in depth]); plt.figure(figsize=(4.6,3)); plt.semilogy(depth,np.maximum(err,1e-12),'o-'); plt.xlabel('maximum braid depth'); plt.ylabel('best projective distance'); plt.title('Fibonacci braid compilation'); save('04_braid_compilation_convergence.pdf')
# 5 projective Bloch orbit
pts=braid_orbit_bloch(6,'fibonacci'); plt.figure(figsize=(4.6,3)); plt.scatter(pts[:,0],pts[:,2],s=7,alpha=.55); plt.xlabel('Bloch x'); plt.ylabel('Bloch z'); plt.title('Finite-depth Fibonacci braid orbit'); save('05_fibonacci_bloch_orbit.pdf')
# 6 Ising vs Fibonacci distinct orbit counts
D=np.arange(0,8); ci=np.array([distinct_projective_orbit_count(int(d),'ising') for d in D]); cf=np.array([distinct_projective_orbit_count(int(d),'fibonacci') for d in D]); plt.figure(figsize=(4.6,3)); plt.plot(D,ci,'o-',label='Ising'); plt.plot(D,cf,'s-',label='Fibonacci'); plt.xlabel('maximum braid depth'); plt.ylabel('distinct Bloch orbit points'); plt.title('Discrete versus expanding braid reachability'); plt.legend(); save('06_ising_vs_fibonacci_reachability.pdf')
# 7 forced measurement success
n=np.arange(0,11); plt.figure(figsize=(4.6,3)); plt.plot(n,[forced_success_probability(.5,int(k)) for k in n],'o-'); plt.xlabel('maximum attempts'); plt.ylabel('success probability'); plt.title('Forced-measurement retry convergence'); save('07_forced_measurement_success.pdf')
# 8 magic-state phase fidelity
d=np.linspace(-np.pi,np.pi,400); plt.figure(figsize=(4.6,3)); plt.plot(d, [magic_state_phase_fidelity(float(x)) for x in d]); plt.xlabel('phase error delta'); plt.ylabel('state fidelity'); plt.title('Magic-state phase-error sensitivity'); save('08_magic_state_phase_fidelity.pdf')
# 9 adiabatic/error acceptance window
split=np.logspace(-4,0,300); gap=1.0; ratio=gap/split; plt.figure(figsize=(4.6,3)); plt.loglog(split,ratio); plt.axhline(10,linestyle=':'); plt.xlabel('residual splitting / gap unit'); plt.ylabel('Tmax / Tmin = gap / splitting'); plt.title('Available adiabatic operation window'); save('09_error_acceptance_window.pdf')
print('generated',len(list(OUT.glob('*.pdf'))),'figures in',OUT)
