from __future__ import annotations
import numpy as np

SIGMA_X=np.array([[0.,1.],[1.,0.]],dtype=complex)
SIGMA_Y=np.array([[0.,-1j],[1j,0.]],dtype=complex)
SIGMA_Z=np.array([[1.,0.],[0.,-1.]],dtype=complex)
I2=np.eye(2,dtype=complex)

def qwz_hamiltonian(kx: float, ky: float, m: float) -> np.ndarray:
    return np.sin(kx)*SIGMA_X + np.sin(ky)*SIGMA_Y + (m+np.cos(kx)+np.cos(ky))*SIGMA_Z

def qwz_velocity_x(kx: float) -> np.ndarray:
    return np.cos(kx)*SIGMA_X - np.sin(kx)*SIGMA_Z

def qwz_velocity_y(ky: float) -> np.ndarray:
    return np.cos(ky)*SIGMA_Y - np.sin(ky)*SIGMA_Z

def kubo_berry_curvature(kx: float, ky: float, m: float) -> float:
    H=qwz_hamiltonian(kx,ky,m)
    evals,evecs=np.linalg.eigh(H)
    u0=evecs[:,0]; u1=evecs[:,1]
    vx=qwz_velocity_x(kx); vy=qwz_velocity_y(ky)
    a=np.vdot(u0,vx@u1)
    b=np.vdot(u1,vy@u0)
    return float(2.0*np.imag(a*b)/(evals[0]-evals[1])**2)

def dvector_berry_curvature(kx: float, ky: float, m: float) -> float:
    d=np.array([np.sin(kx),np.sin(ky),m+np.cos(kx)+np.cos(ky)],dtype=float)
    dkx=np.array([np.cos(kx),0.,-np.sin(kx)],dtype=float)
    dky=np.array([0.,np.cos(ky),-np.sin(ky)],dtype=float)
    return float(-0.5*np.dot(d,np.cross(dkx,dky))/(np.linalg.norm(d)**3))

def kubo_chern_number(m: float, nk: int=41) -> float:
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    total=0.0
    for kx in ks:
        for ky in ks:
            total += kubo_berry_curvature(float(kx),float(ky),m)
    dk=2*np.pi/nk
    return float(total*dk*dk/(2*np.pi))

def hall_conductivity_e2_over_h(m: float, nk: int=41) -> float:
    return kubo_chern_number(m,nk)

def qwz_bulk_gap(m: float, nk: int=101) -> float:
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    gap=np.inf
    for kx in ks:
        for ky in ks:
            e=np.linalg.eigvalsh(qwz_hamiltonian(float(kx),float(ky),m))
            gap=min(gap,float(e[1]-e[0]))
    return float(gap)

def qwz_realspace_torus(L: int, m: float, disorder: float=0.0, seed: int=0) -> np.ndarray:
    if L<2:
        raise ValueError("L must be at least 2.")
    N=2*L*L
    H=np.zeros((N,N),dtype=complex)
    tx=0.5*SIGMA_Z-0.5j*SIGMA_X
    ty=0.5*SIGMA_Z-0.5j*SIGMA_Y
    rng=np.random.default_rng(seed)
    onsite=rng.uniform(-disorder/2,disorder/2,size=L*L) if disorder else np.zeros(L*L)
    def sl(x,y):
        i=2*(y*L+x)
        return slice(i,i+2)
    for y in range(L):
        for x in range(L):
            s=sl(x,y)
            H[s,s] += m*SIGMA_Z + onsite[y*L+x]*I2
            sx=sl((x+1)%L,y)
            sy=sl(x,(y+1)%L)
            H[s,sx]+=tx; H[sx,s]+=tx.conj().T
            H[s,sy]+=ty; H[sy,s]+=ty.conj().T
    return H

def finite_size_spectral_gap(H: np.ndarray, fermi: float=0.0) -> float:
    e=np.linalg.eigvalsh(H)-fermi
    neg=e[e<0]; pos=e[e>=0]
    if len(neg)==0 or len(pos)==0:
        return 0.0
    return float(pos.min()-neg.max())

def _polar_unitary(A: np.ndarray) -> np.ndarray:
    u,_,vh=np.linalg.svd(A)
    return u@vh

def bott_index(H: np.ndarray, L: int, fermi: float=0.0) -> float:
    evals,evecs=np.linalg.eigh(H)
    occ=evecs[:,evals<fermi]
    if occ.shape[1]==0 or occ.shape[1]==H.shape[0]:
        raise ValueError("Fermi level must split occupied and empty states.")
    P=occ@occ.conj().T
    I=np.eye(H.shape[0],dtype=complex)
    px=np.empty(H.shape[0],dtype=complex)
    py=np.empty(H.shape[0],dtype=complex)
    for y in range(L):
        for x in range(L):
            phase_x=np.exp(2j*np.pi*x/L)
            phase_y=np.exp(2j*np.pi*y/L)
            for a in range(2):
                idx=2*(y*L+x)+a
                px[idx]=phase_x; py[idx]=phase_y
    U=_polar_unitary(P@np.diag(px)@P + I-P)
    V=_polar_unitary(P@np.diag(py)@P + I-P)
    W=U@V@U.conj().T@V.conj().T
    return float(np.angle(np.linalg.eigvals(W)).sum()/(2*np.pi))

def qwz_bott_index(L: int, m: float, disorder: float=0.0, seed: int=0) -> float:
    return bott_index(qwz_realspace_torus(L,m,disorder,seed),L)

def disorder_bott_ensemble(L: int, m: float, disorder: float, seeds=range(6)) -> dict:
    vals=np.array([qwz_bott_index(L,m,disorder,int(seed)) for seed in seeds],dtype=float)
    rounded=np.rint(vals).astype(int)
    return {
        "mean": float(vals.mean()),
        "std": float(vals.std()),
        "rounded_values": rounded.tolist(),
        "topological_fraction": float(np.mean(np.abs(rounded)==1)),
    }

def ssh_chain_hamiltonian(ncells: int, t1: float, t2: float,
                          bond_disorder: float=0.0, onsite_disorder: float=0.0,
                          seed: int=0) -> np.ndarray:
    if ncells<1:
        raise ValueError("ncells must be positive.")
    N=2*ncells
    H=np.zeros((N,N),dtype=complex)
    rng=np.random.default_rng(seed)
    for c in range(ncells):
        a,b=2*c,2*c+1
        h1=t1*(1.0+bond_disorder*rng.uniform(-1,1))
        H[a,b]=H[b,a]=h1
        if c<ncells-1:
            h2=t2*(1.0+bond_disorder*rng.uniform(-1,1))
            H[b,a+2]=H[a+2,b]=h2
    if onsite_disorder:
        H += np.diag(onsite_disorder*rng.uniform(-1,1,size=N))
    return H

def wideband_scattering_matrix(H: np.ndarray, E: float=0.0,
                               gamma_left: float=0.6, gamma_right: float=0.6) -> np.ndarray:
    if gamma_left<=0 or gamma_right<=0:
        raise ValueError("Lead broadenings must be positive.")
    N=H.shape[0]
    Sigma=np.zeros_like(H,dtype=complex)
    Sigma[0,0] -= 0.5j*gamma_left
    Sigma[-1,-1] -= 0.5j*gamma_right
    G=np.linalg.inv((E+1e-12j)*np.eye(N)-H-Sigma)
    rL=1.0-1j*gamma_left*G[0,0]
    rR=1.0-1j*gamma_right*G[-1,-1]
    tRL=-1j*np.sqrt(gamma_left*gamma_right)*G[-1,0]
    tLR=-1j*np.sqrt(gamma_left*gamma_right)*G[0,-1]
    return np.array([[rL,tLR],[tRL,rR]],dtype=complex)

def scattering_unitarity_error(S: np.ndarray) -> float:
    return float(np.linalg.norm(S.conj().T@S-np.eye(S.shape[0])))

def ssh_reflection_invariant(ncells: int, t1: float, t2: float,
                             bond_disorder: float=0.0, seed: int=0,
                             gamma: float=0.6) -> int:
    H=ssh_chain_hamiltonian(ncells,t1,t2,bond_disorder=bond_disorder,seed=seed)
    S=wideband_scattering_matrix(H,0.0,gamma,gamma)
    return 1 if np.real(S[0,0])>=0 else -1

def landauer_transmission(H: np.ndarray, E: float=0.0,
                          gamma_left: float=2.0, gamma_right: float=2.0) -> float:
    S=wideband_scattering_matrix(H,E,gamma_left,gamma_right)
    return float(abs(S[1,0])**2)

def uniform_chain(nsites: int, t: float=1.0, onsite: float=0.0,
                  disorder: float=0.0, seed: int=0) -> np.ndarray:
    if nsites<1:
        raise ValueError("nsites must be positive.")
    rng=np.random.default_rng(seed)
    H=np.zeros((nsites,nsites),dtype=complex)
    onsite_vals=np.full(nsites,onsite,dtype=float)
    if disorder:
        onsite_vals += rng.uniform(-disorder/2,disorder/2,size=nsites)
    H[np.diag_indices(nsites)] = onsite_vals
    for i in range(nsites-1):
        H[i,i+1]=H[i+1,i]=-t
    return H

def disorder_averaged_transmission(nsites: int=8, disorder: float=0.0,
                                  seeds=range(20), gamma: float=2.0) -> dict:
    vals=np.array([landauer_transmission(uniform_chain(nsites,disorder=disorder,seed=int(seed)),
                                        gamma_left=gamma,gamma_right=gamma)
                   for seed in seeds],dtype=float)
    return {"mean":float(vals.mean()),"std":float(vals.std()),"min":float(vals.min()),"max":float(vals.max())}

def single_level_transmission(E: float, epsilon: float=0.0,
                              gamma_left: float=1.0, gamma_right: float=1.0) -> float:
    denom=(E-epsilon)**2 + 0.25*(gamma_left+gamma_right)**2
    return float(gamma_left*gamma_right/denom)

def contact_limited_peak_transmission(gamma_left: float, gamma_right: float) -> float:
    if gamma_left<=0 or gamma_right<=0:
        raise ValueError("Lead broadenings must be positive.")
    return float(4*gamma_left*gamma_right/(gamma_left+gamma_right)**2)

def reference_summary() -> dict:
    kubo_top=kubo_chern_number(-1.0,41)
    kubo_triv=kubo_chern_number(3.0,41)
    bott_clean=qwz_bott_index(6,-1.0,0.0,0)
    bott_dis=disorder_bott_ensemble(6,-1.0,2.0,seeds=range(4))
    inv_triv=ssh_reflection_invariant(16,1.2,0.8)
    inv_top=ssh_reflection_invariant(16,0.8,1.2)
    clean_T=landauer_transmission(uniform_chain(8),gamma_left=2.0,gamma_right=2.0)
    dis_T=disorder_averaged_transmission(8,2.0,seeds=range(20),gamma=2.0)
    return {
        "kubo_chern_topological":kubo_top,
        "kubo_chern_trivial":kubo_triv,
        "hall_sigma_xy_e2_over_h_topological":hall_conductivity_e2_over_h(-1.0,41),
        "bott_clean":bott_clean,
        "bott_disorder_W2":bott_dis,
        "ssh_reflection_invariant_trivial":inv_triv,
        "ssh_reflection_invariant_topological":inv_top,
        "clean_chain_transmission":clean_T,
        "disordered_chain_W2":dis_T,
        "asymmetric_contact_peak_T":contact_limited_peak_transmission(1.0,0.25),
    }

if __name__=="__main__":
    import json
    print(json.dumps(reference_summary(),indent=2))
