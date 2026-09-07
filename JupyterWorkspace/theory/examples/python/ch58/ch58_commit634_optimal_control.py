"""Commit 634 numerical companion: shaped and optimal quantum control."""
from __future__ import annotations
import numpy as np

SX=np.array([[0.,1.],[1.,0.]],complex)
SY=np.array([[0.,-1j],[1j,0.]],complex)
SZ=np.array([[1.,0.],[0.,-1.]],complex)
I2=np.eye(2,dtype=complex)

def _trapz(y,x):
    return np.trapezoid(y,x) if hasattr(np,'trapezoid') else np.trapz(y,x)

def gaussian_envelope(t,sigma,area=np.pi,center=None):
    t=np.asarray(t,float)
    if t.ndim!=1 or t.size<3: raise ValueError('t must be a 1D grid')
    if sigma<=0: raise ValueError('sigma must be positive')
    if center is None: center=.5*(t[0]+t[-1])
    g=np.exp(-.5*((t-center)/sigma)**2)
    return g*(float(area)/_trapz(g,t))

def drag_quadrature(t,omega_i,anharmonicity,beta=1.0):
    t=np.asarray(t,float); omega_i=np.asarray(omega_i,float)
    if t.shape!=omega_i.shape: raise ValueError('shape mismatch')
    if anharmonicity==0: raise ValueError('anharmonicity must be nonzero')
    return float(beta)*np.gradient(omega_i,t)/float(anharmonicity)

def pulse_area(t,omega): return float(_trapz(np.asarray(omega,float),np.asarray(t,float)))

def pulse_spectrum(t,omega):
    t=np.asarray(t,float); omega=np.asarray(omega,float); dt=float(np.mean(np.diff(t)))
    w=2*np.pi*np.fft.rfftfreq(t.size,d=dt); a=np.fft.rfft(omega)
    return w,np.abs(a)**2

def rotating_frame_hamiltonian(detuning,omega_i,omega_q):
    return -.5*float(detuning)*SZ+.5*float(omega_i)*SX+.5*float(omega_q)*SY

def hermitian_step(H,dt):
    w,v=np.linalg.eigh(np.asarray(H,complex)); return (v*np.exp(-1j*w*float(dt)))@v.conj().T

def qutrit_propagate(t,omega_i,omega_q=None,anharmonicity=-4.,detuning=0.,initial=None):
    t=np.asarray(t,float); I=np.asarray(omega_i,float); Q=np.zeros_like(I) if omega_q is None else np.asarray(omega_q,float)
    if not(t.shape==I.shape==Q.shape): raise ValueError('shape mismatch')
    a=np.array([[0.,1.,0.],[0.,0.,np.sqrt(2.)],[0.,0.,0.]],complex); ad=a.conj().T
    psi=np.array([1.,0.,0.],complex) if initial is None else np.asarray(initial,complex).copy(); psi/=np.linalg.norm(psi)
    bare=np.diag([0.,-float(detuning),float(anharmonicity)-2*float(detuning)]).astype(complex)
    for k in range(t.size-1):
        c=I[k]-1j*Q[k]; H=bare+.5*(c*ad+np.conj(c)*a); psi=hermitian_step(H,t[k+1]-t[k])@psi
    return psi

def leakage_probability(state,computational_levels=2):
    s=np.asarray(state,complex); return float(max(0.,1.-np.sum(np.abs(s[:computational_levels])**2).real))

def state_population(state,level): return float(abs(np.asarray(state,complex)[int(level)])**2)

def average_gate_fidelity(unitary,target):
    U=np.asarray(unitary,complex); V=np.asarray(target,complex)
    if U.shape!=V.shape or U.shape[0]!=U.shape[1]: raise ValueError('shape mismatch')
    d=U.shape[0]; z=np.trace(V.conj().T@U); return float((abs(z)**2+d)/(d*(d+1.)))

def grape_fidelity_and_gradient(controls,dt,target,drift=None):
    u=np.asarray(controls,float); target=np.asarray(target,complex)
    if u.ndim!=2 or u.shape[1]!=2: raise ValueError('controls must have shape (N,2)')
    if target.shape!=(2,2): raise ValueError('target must be 2x2')
    drift=np.zeros((2,2),complex) if drift is None else np.asarray(drift,complex); hc=(.5*SX,.5*SY)
    steps=[hermitian_step(drift+ux*hc[0]+uy*hc[1],dt) for ux,uy in u]
    prefix=[I2]
    for U in steps: prefix.append(U@prefix[-1])
    total=prefix[-1]; suffix=[None]*len(steps); after=I2
    for k in range(len(steps)-1,-1,-1): suffix[k]=after; after=after@steps[k]
    z=np.trace(target.conj().T@total)/2.; F=float(abs(z)**2); g=np.zeros_like(u)
    for k,Uk in enumerate(steps):
        for c,Hc in enumerate(hc):
            dU=suffix[k]@(-1j*float(dt)*Hc@Uk)@prefix[k]; dz=np.trace(target.conj().T@dU)/2.; g[k,c]=2*np.real(np.conj(z)*dz)
    return F,g,total

def optimize_grape(controls,dt,target,iterations=80,learning_rate=5.,amplitude_limit=2.,drift=None):
    u=np.asarray(controls,float).copy(); hist=[]
    for _ in range(int(iterations)):
        F,g,_=grape_fidelity_and_gradient(u,dt,target,drift); hist.append(F); u+=float(learning_rate)*g
        if amplitude_limit is not None: u=np.clip(u,-abs(float(amplitude_limit)),abs(float(amplitude_limit)))
    F,_,U=grape_fidelity_and_gradient(u,dt,target,drift); hist.append(F); return u,np.asarray(hist),U

def switching_filter(t,modulation,angular_frequencies):
    t=np.asarray(t,float); y=np.asarray(modulation,float); w=np.asarray(angular_frequencies,float)
    if t.shape!=y.shape: raise ValueError('shape mismatch')
    phase=np.exp(1j*np.outer(w,t)); vals=np.array([_trapz(p*y,t) for p in phase]); return abs(vals)**2

def spectral_overlap(t,modulation,angular_frequencies,noise_psd):
    w=np.asarray(angular_frequencies,float); S=np.asarray(noise_psd,float)
    if w.shape!=S.shape: raise ValueError('shape mismatch')
    return float(_trapz(S*switching_filter(t,modulation,w),w)/np.pi)

def rb_survival(lengths,p,A=.5,B=.5): return float(A)*(float(p)**np.asarray(lengths,float))+float(B)

def rb_error_per_clifford(p,dimension=2):
    d=int(dimension)
    if d<2: raise ValueError('dimension must be >=2')
    return float((d-1.)*(1.-float(p))/d)

def gaussian_pi_benchmark(alpha=-4.,sigma=.65,beta=1.,points=1201):
    t=np.linspace(-3.,3.,int(points)); I=gaussian_envelope(t,sigma,np.pi); Q=drag_quadrature(t,I,alpha,beta)
    plain=qutrit_propagate(t,I,anharmonicity=alpha); drag=qutrit_propagate(t,I,Q,anharmonicity=alpha)
    return {'t':t,'I':I,'Q_drag':Q,'plain_state':plain,'drag_state':drag,'plain_leakage':leakage_probability(plain),'drag_leakage':leakage_probability(drag)}
