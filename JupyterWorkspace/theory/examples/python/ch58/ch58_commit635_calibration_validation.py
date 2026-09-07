from __future__ import annotations
import numpy as np
I2=np.eye(2,dtype=complex)
SX=np.array([[0,1],[1,0]],complex); SY=np.array([[0,-1j],[1j,0]],complex); SZ=np.array([[1,0],[0,-1]],complex)
PAULIS=(I2,SX,SY,SZ)
def hermitian_step(H,dt=1.0):
    w,v=np.linalg.eigh(np.asarray(H,complex)); return (v*np.exp(-1j*w*float(dt)))@v.conj().T
def unitary_rotation(axis,angle):
    a=np.asarray(axis,float); n=np.linalg.norm(a)
    if n==0: raise ValueError('axis must be nonzero')
    a=a/n; return hermitian_step(.5*(a[0]*SX+a[1]*SY+a[2]*SZ),angle)
def average_gate_fidelity(U,V):
    U=np.asarray(U,complex); V=np.asarray(V,complex)
    if U.shape!=V.shape or U.ndim!=2 or U.shape[0]!=U.shape[1]: raise ValueError('shape mismatch')
    d=U.shape[0]; z=np.trace(V.conj().T@U); return float((abs(z)**2+d)/(d*(d+1)))
def pauli_transfer_from_unitary(U):
    U=np.asarray(U,complex)
    if U.shape!=(2,2): raise ValueError('U must be 2x2')
    R=np.zeros((4,4))
    for i,Pi in enumerate(PAULIS):
        for j,Pj in enumerate(PAULIS): R[i,j]=.5*np.trace(Pi@U@Pj@U.conj().T).real
    return R
def amplitude_damping_kraus(gamma):
    g=float(gamma)
    if not 0<=g<=1: raise ValueError('gamma must be in [0,1]')
    return [np.array([[1,0],[0,np.sqrt(1-g)]],complex),np.array([[0,np.sqrt(g)],[0,0]],complex)]
def choi_from_kraus(kraus):
    ks=[np.asarray(k,complex) for k in kraus]
    if not ks: raise ValueError('Kraus list empty')
    d=ks[0].shape[0]; phi=np.eye(d,dtype=complex).reshape(-1)/np.sqrt(d); rho=np.outer(phi,phi.conj()); out=np.zeros_like(rho)
    for K in ks:
        A=np.kron(np.eye(d),K); out+=A@rho@A.conj().T
    return out
def calibration_fidelity_map(target_angle=np.pi,amplitude_errors=None,detunings=None):
    a=np.linspace(-.1,.1,41) if amplitude_errors is None else np.asarray(amplitude_errors,float)
    d=np.linspace(-.2,.2,41) if detunings is None else np.asarray(detunings,float)
    target=unitary_rotation((1,0,0),target_angle); F=np.zeros((d.size,a.size))
    for i,dd in enumerate(d):
        for j,e in enumerate(a): F[i,j]=average_gate_fidelity(hermitian_step(.5*((1+e)*SX+dd*SZ),target_angle),target)
    return a,d,F
def rb_survival(lengths,p,A=.5,B=.5): return float(A)*float(p)**np.asarray(lengths,float)+float(B)
def rb_error_per_clifford(p,dimension=2):
    d=int(dimension)
    if d<2: raise ValueError('dimension')
    return float((d-1)*(1-float(p))/d)
def interleaved_rb_gate_error(p_reference,p_interleaved,dimension=2):
    pr=float(p_reference); pi=float(p_interleaved); d=int(dimension)
    if pr<=0: raise ValueError('reference p')
    return float((d-1)*(1-pi/pr)/d)
def leakage_rb_survival(lengths,leakage_rate,A=1.0,floor=0.0):
    l=float(leakage_rate)
    if not 0<=l<1: raise ValueError('leakage')
    m=np.asarray(lengths,float); return float(floor)+(float(A)-float(floor))*(1-l)**m
def coherent_overrotation_survival(lengths,epsilon,stochastic_decay=1.0):
    m=np.asarray(lengths,float); return .5+.5*float(stochastic_decay)**m*np.cos(m*float(epsilon))
def unitarity_proxy(R):
    R=np.asarray(R,float)
    if R.shape!=(4,4): raise ValueError('PTM')
    s=np.linalg.svd(R[1:,1:],compute_uv=False); return float(np.mean(s*s))
def first_order_lowpass(command,alpha):
    x=np.asarray(command,float); a=float(alpha)
    if not 0<=a<1: raise ValueError('alpha')
    y=np.zeros_like(x)
    if x.size:
        y[0]=(1-a)*x[0]
        for k in range(1,x.size): y[k]=(1-a)*x[k]+a*y[k-1]
    return y
def robustness_summary(F):
    x=np.asarray(F,float); return {'mean':float(x.mean()),'minimum':float(x.min()),'maximum':float(x.max()),'std':float(x.std())}
def pareto_mask(costs):
    C=np.asarray(costs,float)
    if C.ndim!=2: raise ValueError('costs')
    out=np.ones(C.shape[0],bool)
    for i in range(C.shape[0]):
        better=np.all(C<=C[i],axis=1)&np.any(C<C[i],axis=1); better[i]=False
        if np.any(better): out[i]=False
    return out
def calibration_drift_trace(steps=200,sigma=.002,seed=1):
    return np.cumsum(np.random.default_rng(seed).normal(0,float(sigma),int(steps)))
def gate_score(infidelity,leakage,duration,power,weights=(1,1,0,0)):
    return float(np.array([infidelity,leakage,duration,power])@np.asarray(weights,float))
