from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
OUT=Path(__file__).resolve().parents[3]/"generated/ch04"; OUT.mkdir(parents=True,exist_ok=True)
def euler(f,t,y0):
 y=np.empty_like(t); y[0]=y0
 for n in range(len(t)-1):
  h=t[n+1]-t[n]; y[n+1]=y[n]+h*f(t[n],y[n])
 return y
def rk4(f,t,y0):
 y=np.empty_like(t); y[0]=y0
 for n in range(len(t)-1):
  h=t[n+1]-t[n]; k1=f(t[n],y[n]); k2=f(t[n]+h/2,y[n]+h*k1/2); k3=f(t[n]+h/2,y[n]+h*k2/2); k4=f(t[n]+h,y[n]+h*k3); y[n+1]=y[n]+h*(k1+2*k2+2*k3+k4)/6
 return y
f=lambda t,y:-2*y
t=np.linspace(0,3,31); exact=np.exp(-2*t); ye=euler(f,t,1.); yr=rk4(f,t,1.)
plt.figure(); plt.plot(t,exact,label='exact'); plt.plot(t,ye,'o-',label='Euler'); plt.plot(t,yr,'--',label='RK4'); plt.xlabel('t'); plt.ylabel('y'); plt.legend(); plt.tight_layout(); plt.savefig(OUT/'numerical_decay.pdf'); plt.close()
hs=2.0**(-np.arange(2,8)); ee=[]; er=[]
for h in hs:
 tt=np.arange(0,1+h/2,h); ee.append(abs(euler(f,tt,1.)[-1]-np.exp(-2))); er.append(abs(rk4(f,tt,1.)[-1]-np.exp(-2)))
plt.figure(); plt.loglog(hs,ee,'o-',label='Euler'); plt.loglog(hs,er,'o-',label='RK4'); plt.xlabel('step h'); plt.ylabel('error'); plt.legend(); plt.tight_layout(); plt.savefig(OUT/'convergence.pdf'); plt.close()
def vf(t,z): return np.array([z[1],z[0]-z[0]**3-0.2*z[1]])
tt=np.linspace(0,30,6001); z=np.empty((len(tt),2)); z[0]=[0.2,0.8]
for n in range(len(tt)-1):
 h=tt[n+1]-tt[n]; k1=vf(tt[n],z[n]); k2=vf(tt[n]+h/2,z[n]+h*k1/2); k3=vf(tt[n]+h/2,z[n]+h*k2/2); k4=vf(tt[n]+h,z[n]+h*k3); z[n+1]=z[n]+h*(k1+2*k2+2*k3+k4)/6
plt.figure(); plt.plot(z[:,0],z[:,1]); plt.xlabel('x'); plt.ylabel('v'); plt.tight_layout(); plt.savefig(OUT/'phase_portrait.pdf'); plt.close()
om=np.linspace(0,2,500); A=1/np.sqrt((1-om*om)**2+(0.16*om)**2)
plt.figure(); plt.plot(om,A); plt.xlabel('driving frequency'); plt.ylabel('amplitude'); plt.tight_layout(); plt.savefig(OUT/'resonance_curve.pdf'); plt.close()
print(f'Euler finest-grid error: {ee[-1]:.8e}'); print(f'RK4 finest-grid error: {er[-1]:.8e}')
