from __future__ import annotations
import numpy as np

SIGMA_X=np.array([[0.0,1.0],[1.0,0.0]],dtype=complex)
SIGMA_Y=np.array([[0.0,-1j],[1j,0.0]],dtype=complex)
SIGMA_Z=np.array([[1.0,0.0],[0.0,-1.0]],dtype=complex)
I2=np.eye(2,dtype=complex)


def hermitian_exponential(H: np.ndarray, t: float) -> np.ndarray:
    vals,vecs=np.linalg.eigh(H)
    return vecs @ np.diag(np.exp(-1j*vals*t)) @ vecs.conj().T


def qwz_hamiltonian(kx: float, ky: float, m: float) -> np.ndarray:
    return (np.sin(kx)*SIGMA_X + np.sin(ky)*SIGMA_Y +
            (m+np.cos(kx)+np.cos(ky))*SIGMA_Z)


def floquet_square_pulse_operator(kx: float, ky: float, m_a: float=3.0,
                                  m_b: float=-3.0, period: float=0.6) -> np.ndarray:
    if period<=0:
        raise ValueError('period must be positive.')
    Ua=hermitian_exponential(qwz_hamiltonian(kx,ky,m_a),period/2)
    Ub=hermitian_exponential(qwz_hamiltonian(kx,ky,m_b),period/2)
    return Ub@Ua


def floquet_unitarity_error(**kwargs) -> float:
    U=floquet_square_pulse_operator(0.37,-0.61,**kwargs)
    return float(np.linalg.norm(U.conj().T@U-I2))


def floquet_quasienergies_and_vectors(kx: float, ky: float, m_a: float=3.0,
                                       m_b: float=-3.0, period: float=0.6):
    U=floquet_square_pulse_operator(kx,ky,m_a,m_b,period)
    vals,vecs=np.linalg.eig(U)
    eps=-np.angle(vals)/period
    order=np.argsort(eps)
    vecs=vecs[:,order]
    for j in range(vecs.shape[1]):
        vecs[:,j]/=np.linalg.norm(vecs[:,j])
    return eps[order].astype(float),vecs


def floquet_effective_hamiltonian(kx: float, ky: float, m_a: float=3.0,
                                   m_b: float=-3.0, period: float=0.6) -> np.ndarray:
    eps,vecs=floquet_quasienergies_and_vectors(kx,ky,m_a,m_b,period)
    Hf=vecs@np.diag(eps)@np.linalg.inv(vecs)
    return 0.5*(Hf+Hf.conj().T)


def floquet_reconstruction_error(kx: float=0.41, ky: float=-0.73,
                                  m_a: float=3.0, m_b: float=-3.0,
                                  period: float=0.6) -> float:
    U=floquet_square_pulse_operator(kx,ky,m_a,m_b,period)
    Hf=floquet_effective_hamiltonian(kx,ky,m_a,m_b,period)
    Ur=hermitian_exponential(Hf,period)
    return float(np.linalg.norm(U-Ur))


def floquet_band_chern(m_a: float=3.0, m_b: float=-3.0,
                       period: float=0.6, nk: int=31) -> int:
    if nk<7:
        raise ValueError('nk must be at least 7.')
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    u=np.empty((nk,nk,2),dtype=complex)
    for i,kx in enumerate(ks):
        for j,ky in enumerate(ks):
            _,vecs=floquet_quasienergies_and_vectors(float(kx),float(ky),m_a,m_b,period)
            u[i,j]=vecs[:,0]
    total=0.0
    def link(a,b):
        z=np.vdot(a,b)
        if abs(z)<1e-13:
            raise FloatingPointError('Floquet link overlap became too small.')
        return z/abs(z)
    for i in range(nk):
        ip=(i+1)%nk
        for j in range(nk):
            jp=(j+1)%nk
            ux=link(u[i,j],u[ip,j])
            uy=link(u[i,j],u[i,jp])
            ux_y=link(u[i,jp],u[ip,jp])
            uy_x=link(u[ip,j],u[ip,jp])
            total+=np.angle(ux*uy_x/(ux_y*uy))
    return int(np.rint(total/(2*np.pi)))


def floquet_zero_pi_gaps(m_a: float=3.0, m_b: float=-3.0,
                          period: float=0.6, nk: int=41) -> dict:
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    g0=np.inf;gpi=np.inf
    for kx in ks:
        for ky in ks:
            eps,_=floquet_quasienergies_and_vectors(float(kx),float(ky),m_a,m_b,period)
            ae=np.abs(eps)
            g0=min(g0,2*float(np.min(ae)))
            gpi=min(gpi,2*float(np.min(np.pi/period-ae)))
    return {'zero_gap':float(g0),'pi_gap':float(gpi)}


def stroboscopic_state(Uf: np.ndarray, psi0: np.ndarray, periods: int) -> np.ndarray:
    if periods<0:
        raise ValueError('periods must be nonnegative.')
    psi=np.asarray(psi0,dtype=complex)
    for _ in range(periods):
        psi=Uf@psi
    return psi


def ssh_hamiltonian(k: float, t1: float, t2: float) -> np.ndarray:
    return (t1+t2*np.cos(k))*SIGMA_X+t2*np.sin(k)*SIGMA_Y


def occupied_vector(H: np.ndarray) -> np.ndarray:
    vals,vecs=np.linalg.eigh(H)
    return vecs[:,np.argmin(vals)]


def loschmidt_amplitude(k: float, t: float, initial=(1.4,0.6), final=(0.6,1.4)) -> complex:
    ui=occupied_vector(ssh_hamiltonian(k,*initial))
    U=hermitian_exponential(ssh_hamiltonian(k,*final),t)
    return complex(np.vdot(ui,U@ui))


def loschmidt_rate(t: float, initial=(1.4,0.6), final=(0.6,1.4), nk: int=801) -> float:
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    vals=[]
    for k in ks:
        g=loschmidt_amplitude(float(k),t,initial,final)
        vals.append(max(abs(g)**2,1e-15))
    return float(-np.mean(np.log(vals)))


def post_quench_excitation_probability(k: float, initial=(1.4,0.6), final=(0.6,1.4)) -> float:
    ui=occupied_vector(ssh_hamiltonian(k,*initial))
    vals,vf=np.linalg.eigh(ssh_hamiltonian(k,*final))
    upper=vf[:,np.argmax(vals)]
    return float(abs(np.vdot(upper,ui))**2)


def quench_excitation_density(initial=(1.4,0.6), final=(0.6,1.4), nk: int=801) -> float:
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    return float(np.mean([post_quench_excitation_probability(float(k),initial,final) for k in ks]))


def quench_critical_mode(initial=(1.4,0.6), final=(0.6,1.4), nk: int=4001) -> dict:
    ks=np.linspace(0,np.pi,nk)
    p=np.array([post_quench_excitation_probability(float(k),initial,final) for k in ks])
    idx=int(np.argmin(abs(p-0.5)))
    k=float(ks[idx]); prob=float(p[idx])
    E=float(np.max(np.linalg.eigvalsh(ssh_hamiltonian(k,*final))))
    tstar=float(np.pi/(2*E))
    return {'k':k,'excitation_probability':prob,'first_critical_time':tstar}


def chain_hamiltonian(length: int=101, hopping: float=1.0, disorder: float=0.0,
                      seed: int=0) -> np.ndarray:
    if length<3 or hopping==0 or disorder<0:
        raise ValueError('Require length>=3, hopping!=0, disorder>=0.')
    H=np.zeros((length,length),dtype=complex)
    for i in range(length-1):
        H[i,i+1]=H[i+1,i]=-hopping
    if disorder:
        rng=np.random.default_rng(seed)
        H+=np.diag(rng.uniform(-disorder/2,disorder/2,length))
    return H


def delta_packet(length: int=101, site: int|None=None) -> np.ndarray:
    if length<1:
        raise ValueError('length must be positive.')
    if site is None: site=length//2
    if site<0 or site>=length:
        raise ValueError('site outside chain.')
    psi=np.zeros(length,dtype=complex);psi[site]=1.0
    return psi


def evolve_state(H: np.ndarray, psi0: np.ndarray, t: float) -> np.ndarray:
    return hermitian_exponential(H,t)@np.asarray(psi0,dtype=complex)


def packet_diagnostics(psi: np.ndarray) -> dict:
    p=np.abs(np.asarray(psi))**2
    norm=float(np.sum(p))
    x=np.arange(len(p),dtype=float)
    mean=float(np.sum(x*p)/norm)
    variance=float(np.sum((x-mean)**2*p)/norm)
    ipr=float(np.sum((p/norm)**2))
    return {'norm':norm,'mean':mean,'variance':variance,'ipr':ipr}


def clean_ballistic_variance(t: float, hopping: float=1.0) -> float:
    return float(2*(hopping*t)**2)


def disorder_packet_ensemble(t: float, length: int=81, hopping: float=1.0,
                             disorder: float=4.0, seeds=range(5)) -> dict:
    vals=[];iprs=[]
    psi0=delta_packet(length)
    for seed in seeds:
        psi=evolve_state(chain_hamiltonian(length,hopping,disorder,int(seed)),psi0,t)
        d=packet_diagnostics(psi);vals.append(d['variance']);iprs.append(d['ipr'])
    return {'mean_variance':float(np.mean(vals)),'std_variance':float(np.std(vals)),
            'mean_ipr':float(np.mean(iprs))}


def spreading_exponent(times, variances) -> float:
    t=np.asarray(times,dtype=float);v=np.asarray(variances,dtype=float)
    if len(t)<2 or np.any(t<=0) or np.any(v<=0):
        raise ValueError('Need at least two positive times and variances.')
    slope,_=np.polyfit(np.log(t),np.log(v),1)
    return float(slope)


def qwz_open_hamiltonian(L: int, m: float) -> np.ndarray:
    if L<2:
        raise ValueError('L must be at least 2.')
    N=2*L*L;H=np.zeros((N,N),dtype=complex)
    tx=0.5*SIGMA_Z-0.5j*SIGMA_X
    ty=0.5*SIGMA_Z-0.5j*SIGMA_Y
    def sl(x,y):
        i=2*(y*L+x);return slice(i,i+2)
    for y in range(L):
        for x in range(L):
            s=sl(x,y);H[s,s]+=m*SIGMA_Z
            if x+1<L:
                q=sl(x+1,y);H[s,q]+=tx;H[q,s]+=tx.conj().T
            if y+1<L:
                q=sl(x,y+1);H[s,q]+=ty;H[q,s]+=ty.conj().T
    return H


def half_filled_projector(H: np.ndarray) -> np.ndarray:
    vals,vecs=np.linalg.eigh(H)
    occ=vecs[:,:H.shape[0]//2]
    return occ@occ.conj().T


def evolve_projector(P: np.ndarray, H: np.ndarray, t: float) -> np.ndarray:
    U=hermitian_exponential(H,t)
    return U@P@U.conj().T


def local_chern_marker_from_projector(P: np.ndarray, L: int) -> np.ndarray:
    Q=np.eye(P.shape[0],dtype=complex)-P
    xs=[];ys=[]
    for y in range(L):
        for x in range(L):
            xs.extend([float(x),float(x)]);ys.extend([float(y),float(y)])
    X=np.diag(xs);Y=np.diag(ys)
    diag=-4*np.pi*np.imag(np.diag(Q@X@P@Y@Q))
    return diag.reshape(L*L,2).sum(axis=1).reshape(L,L)


def bulk_marker_average(marker: np.ndarray, margin: int=1) -> float:
    L=marker.shape[0]
    if marker.ndim!=2 or marker.shape[1]!=L or margin<0 or 2*margin>=L:
        raise ValueError('Invalid marker or margin.')
    core=marker[margin:L-margin,margin:L-margin] if margin else marker
    return float(np.mean(core))


def quench_local_marker(L: int=5, m_initial: float=3.0, m_final: float=-1.0,
                        t: float=1.0, margin: int=1) -> dict:
    Pi=half_filled_projector(qwz_open_hamiltonian(L,m_initial))
    Pt=evolve_projector(Pi,qwz_open_hamiltonian(L,m_final),t)
    marker=local_chern_marker_from_projector(Pt,L)
    return {'bulk_marker':bulk_marker_average(marker,margin),
            'total_marker':float(np.sum(marker)),
            'projector_error':float(np.linalg.norm(Pt@Pt-Pt))}


def quench_state_chern(m_initial: float=3.0, m_final: float=-1.0,
                       t: float=1.0, nk: int=25) -> int:
    ks=np.linspace(-np.pi,np.pi,nk,endpoint=False)
    u=np.empty((nk,nk,2),dtype=complex)
    for i,kx in enumerate(ks):
        for j,ky in enumerate(ks):
            ui=occupied_vector(qwz_hamiltonian(float(kx),float(ky),m_initial))
            u[i,j]=hermitian_exponential(qwz_hamiltonian(float(kx),float(ky),m_final),t)@ui
    def link(a,b):
        z=np.vdot(a,b);return z/abs(z)
    total=0.0
    for i in range(nk):
        ip=(i+1)%nk
        for j in range(nk):
            jp=(j+1)%nk
            ux=link(u[i,j],u[ip,j]);uy=link(u[i,j],u[i,jp])
            ux_y=link(u[i,jp],u[ip,jp]);uy_x=link(u[ip,j],u[ip,jp])
            total+=np.angle(ux*uy_x/(ux_y*uy))
    return int(np.rint(total/(2*np.pi)))


def reference_summary() -> dict:
    gaps=floquet_zero_pi_gaps(3.0,-3.0,0.6,31)
    critical=quench_critical_mode(nk=2001)
    times=np.array([1.0,2.0,3.0,4.0,5.0])
    H=chain_hamiltonian(101,1.0,0.0,0);psi0=delta_packet(101)
    vars_=[packet_diagnostics(evolve_state(H,psi0,float(t)))['variance'] for t in times]
    dis=disorder_packet_ensemble(8.0,81,1.0,4.0,range(5))
    marker=quench_local_marker(5,3.0,-1.0,1.0,1)
    return {
        'floquet_unitarity_error':floquet_unitarity_error(m_a=3.0,m_b=-3.0,period=0.6),
        'floquet_reconstruction_error':floquet_reconstruction_error(period=0.6),
        'floquet_chern_trivial_halves':floquet_band_chern(3.0,-3.0,0.6,25),
        'floquet_zero_gap':gaps['zero_gap'],'floquet_pi_gap':gaps['pi_gap'],
        'quench_excitation_density':quench_excitation_density(nk=801),
        'quench_critical_mode':critical,
        'loschmidt_rate_tstar':loschmidt_rate(critical['first_critical_time'],nk=801),
        'clean_variance_t5':vars_[-1],
        'clean_spreading_exponent':spreading_exponent(times,vars_),
        'disordered_variance_t8_W4':dis['mean_variance'],
        'disordered_ipr_t8_W4':dis['mean_ipr'],
        'quench_local_marker_t1':marker,
        'closed_state_chern_t2':quench_state_chern(3.0,-1.0,2.0,21),
    }

if __name__=='__main__':
    import json
    print(json.dumps(reference_summary(),indent=2))
