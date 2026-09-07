from __future__ import annotations
import numpy as np
from kubo_disorder_scattering_lab import (
    SIGMA_X,SIGMA_Y,SIGMA_Z,I2,
    qwz_hamiltonian,qwz_velocity_x,qwz_velocity_y,
)

def dynamic_hall_chern_units(m: float, omega: float=0.0, eta: float=0.05, nk: int=41) -> complex:
    if eta <= 0 or nk < 5:
        raise ValueError("eta must be positive and nk at least 5.")
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    z=complex(omega,eta)
    total=0.0+0.0j
    for kx in ks:
        for ky in ks:
            H=qwz_hamiltonian(float(kx),float(ky),m)
            evals,evecs=np.linalg.eigh(H)
            uv=evecs[:,0]; uc=evecs[:,1]
            gap=float(evals[1]-evals[0])
            a=np.vdot(uv,qwz_velocity_x(float(kx))@uc)
            b=np.vdot(uc,qwz_velocity_y(float(ky))@uv)
            total += 2.0*np.imag(a*b)/(gap*gap-z*z)
    dk=2*np.pi/nk
    return complex(total*dk*dk/(2*np.pi))

def optical_sigma_xx_e2_over_hbar(m: float, omega: float, eta: float=0.08, nk: int=51) -> float:
    if eta <= 0 or omega < 0 or nk < 5:
        raise ValueError("Require eta>0, omega>=0, nk>=5.")
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    total=0.0
    for kx in ks:
        for ky in ks:
            H=qwz_hamiltonian(float(kx),float(ky),m)
            evals,evecs=np.linalg.eigh(H)
            uv=evecs[:,0]; uc=evecs[:,1]
            gap=float(evals[1]-evals[0])
            mat=abs(np.vdot(uv,qwz_velocity_x(float(kx))@uc))**2
            lor=eta/np.pi/((omega-gap)**2+eta**2)
            total += np.pi*mat*lor/gap
    dk=2*np.pi/nk
    return float(total*dk*dk/(2*np.pi)**2)

def optical_spectrum(m: float, omegas, eta: float=0.08, nk: int=41) -> np.ndarray:
    return np.array([optical_sigma_xx_e2_over_hbar(m,float(w),eta,nk) for w in omegas],dtype=float)

def qwz_open_hamiltonian(L: int, m: float, disorder: float=0.0, seed: int=0) -> np.ndarray:
    if L < 2 or disorder < 0:
        raise ValueError("Require L>=2 and disorder>=0.")
    N=2*L*L
    H=np.zeros((N,N),dtype=complex)
    tx=0.5*SIGMA_Z-0.5j*SIGMA_X
    ty=0.5*SIGMA_Z-0.5j*SIGMA_Y
    rng=np.random.default_rng(seed)
    onsite=rng.uniform(-disorder/2,disorder/2,L*L) if disorder else np.zeros(L*L)
    def sl(x,y):
        i=2*(y*L+x)
        return slice(i,i+2)
    for y in range(L):
        for x in range(L):
            s=sl(x,y)
            H[s,s]+=m*SIGMA_Z+onsite[y*L+x]*I2
            if x+1<L:
                sx=sl(x+1,y); H[s,sx]+=tx; H[sx,s]+=tx.conj().T
            if y+1<L:
                sy=sl(x,y+1); H[s,sy]+=ty; H[sy,s]+=ty.conj().T
    return H

def local_chern_marker(L: int, m: float, disorder: float=0.0, seed: int=0,
                       fermi: float=0.0) -> np.ndarray:
    H=qwz_open_hamiltonian(L,m,disorder,seed)
    evals,evecs=np.linalg.eigh(H)
    occ=evecs[:,evals<fermi]
    if occ.shape[1]==0 or occ.shape[1]==H.shape[0]:
        raise ValueError("Fermi level must split occupied and empty states.")
    P=occ@occ.conj().T
    Q=np.eye(H.shape[0],dtype=complex)-P
    xs=[]; ys=[]
    for y in range(L):
        for x in range(L):
            xs.extend([float(x),float(x)])
            ys.extend([float(y),float(y)])
    X=np.diag(xs); Y=np.diag(ys)
    diag=-4*np.pi*np.imag(np.diag(Q@X@P@Y@Q))
    return diag.reshape(L*L,2).sum(axis=1).reshape(L,L)

def bulk_marker_average(marker: np.ndarray, margin: int=2) -> float:
    if marker.ndim!=2 or marker.shape[0]!=marker.shape[1]:
        raise ValueError("marker must be a square 2D array.")
    L=marker.shape[0]
    if margin<0 or 2*margin>=L:
        raise ValueError("invalid margin.")
    core=marker[margin:L-margin,margin:L-margin] if margin else marker
    return float(np.mean(core))

def disorder_bulk_marker_ensemble(L: int, m: float, disorder: float,
                                  seeds=range(4), margin: int=2) -> dict:
    vals=np.array([bulk_marker_average(local_chern_marker(L,m,disorder,int(s)),margin)
                   for s in seeds],dtype=float)
    return {"mean":float(vals.mean()),"std":float(vals.std()),
            "min":float(vals.min()),"max":float(vals.max())}

def transfer_matrix_1d(E: float, epsilon: float, t: float=1.0) -> np.ndarray:
    if t==0:
        raise ValueError("t must be nonzero.")
    return np.array([[(E-epsilon)/t,-1.0],[1.0,0.0]],dtype=float)

def lyapunov_exponent_1d(E: float=0.0, t: float=1.0, disorder: float=1.0,
                         length: int=20000, seed: int=0) -> float:
    if t==0 or disorder<0 or length<100:
        raise ValueError("Require t!=0, disorder>=0, length>=100.")
    rng=np.random.default_rng(seed)
    eps=rng.uniform(-disorder/2,disorder/2,length) if disorder else np.zeros(length)
    v=np.array([1.0,0.371],dtype=float)
    acc=0.0
    for en in eps:
        v=transfer_matrix_1d(E,float(en),t)@v
        norm=float(np.linalg.norm(v))
        if norm==0 or not np.isfinite(norm):
            raise FloatingPointError("Transfer vector became singular.")
        acc += np.log(norm)
        v /= norm
    return float(max(acc/length,0.0))

def localization_length_1d(**kwargs) -> float:
    gamma=lyapunov_exponent_1d(**kwargs)
    return float(np.inf if gamma<=1e-14 else 1.0/gamma)

def clean_evanescent_lyapunov(E: float, t: float=1.0) -> float:
    if t==0:
        raise ValueError("t must be nonzero.")
    x=abs(E)/(2*abs(t))
    return 0.0 if x<=1 else float(np.arccosh(x))

def averaged_localization_length(E: float, t: float, disorder: float,
                                 length: int=20000, seeds=range(4)) -> float:
    gammas=np.array([lyapunov_exponent_1d(E,t,disorder,length,int(s)) for s in seeds],dtype=float)
    g=float(gammas.mean())
    return float(np.inf if g<=1e-14 else 1.0/g)

def weak_disorder_scaling_fit(disorders=(0.6,0.8,1.0,1.2,1.5),
                              length: int=20000, seeds=range(4)) -> dict:
    W=np.array(disorders,dtype=float)
    if np.any(W<=0):
        raise ValueError("Disorders must be positive.")
    xi=np.array([averaged_localization_length(0.0,1.0,float(w),length,seeds) for w in W])
    slope,intercept=np.polyfit(np.log(W),np.log(xi),1)
    return {"slope":float(slope),"intercept":float(intercept),
            "disorders":W.tolist(),"localization_lengths":xi.tolist()}

def typical_transmission_from_xi(length: float, xi: float) -> float:
    if length<0 or xi<=0:
        raise ValueError("Require length>=0 and xi>0.")
    return float(np.exp(-2.0*length/xi))

def marker_disorder_curve(L: int=8, m: float=-1.0,
                          disorders=(0.0,2.0,4.0,5.0,6.0),
                          seeds=range(3), margin: int=2) -> dict:
    vals=[]
    for W in disorders:
        ens=disorder_bulk_marker_ensemble(L,m,float(W),seeds,margin)
        vals.append(ens["mean"])
    return {"disorders":[float(w) for w in disorders],"mean_markers":vals}

def critical_disorder_proxy(curve: dict, target: float=0.5) -> float:
    W=np.asarray(curve["disorders"],dtype=float)
    M=np.abs(np.asarray(curve["mean_markers"],dtype=float))
    if len(W)<2 or not np.all(np.diff(W)>0):
        raise ValueError("Disorders must be strictly increasing.")
    for i in range(len(W)-1):
        a,b=M[i]-target,M[i+1]-target
        if a==0:
            return float(W[i])
        if a*b<=0:
            if M[i+1]==M[i]:
                return float(0.5*(W[i]+W[i+1]))
            return float(W[i]+(target-M[i])*(W[i+1]-W[i])/(M[i+1]-M[i]))
    raise ValueError("Target is not bracketed by the curve.")

def reference_summary() -> dict:
    dc=dynamic_hall_chern_units(-1.0,omega=0.0,eta=1e-3,nk=41)
    optical_low=optical_sigma_xx_e2_over_hbar(-1.0,0.5,0.08,41)
    optical_edge=optical_sigma_xx_e2_over_hbar(-1.0,2.0,0.08,41)
    marker_clean=bulk_marker_average(local_chern_marker(8,-1.0,0.0,0),2)
    marker_w2=disorder_bulk_marker_ensemble(8,-1.0,2.0,range(3),2)
    xi_w1=averaged_localization_length(0.0,1.0,1.0,16000,range(4))
    fit=weak_disorder_scaling_fit(length=12000,seeds=range(3))
    curve=marker_disorder_curve(8,-1.0,(0.0,2.0,4.0,5.0,6.0),range(3),2)
    wc=critical_disorder_proxy(curve,0.5)
    return {
        "dynamic_hall_dc_real":float(np.real(dc)),
        "dynamic_hall_dc_imag":float(np.imag(dc)),
        "optical_low":optical_low,
        "optical_near_gap":optical_edge,
        "bulk_marker_clean_L8":marker_clean,
        "bulk_marker_W2_L8":marker_w2,
        "xi_W1":xi_w1,
        "weak_disorder_slope":fit["slope"],
        "marker_curve_L8":curve,
        "marker_half_proxy_W":wc,
        "clean_gamma_E2p5":clean_evanescent_lyapunov(2.5,1.0),
    }

if __name__=="__main__":
    import json
    print(json.dumps(reference_summary(),indent=2))
