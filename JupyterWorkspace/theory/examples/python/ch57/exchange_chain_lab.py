from __future__ import annotations
import numpy as np

SX = np.array([[0,1],[1,0]], dtype=complex)
SY = np.array([[0,-1j],[1j,0]], dtype=complex)
SZ = np.array([[1,0],[0,-1]], dtype=complex)
I2 = np.eye(2, dtype=complex)
PAULI = (SX,SY,SZ)
SPIN = tuple(0.5*s for s in PAULI)


def op_on_site(op: np.ndarray, site: int, n: int) -> np.ndarray:
    if not (0 <= site < n):
        raise ValueError('site out of range')
    out = np.array([[1.0+0j]])
    for j in range(n):
        out = np.kron(out, op if j == site else I2)
    return out


def two_site_op(op_i: np.ndarray, i: int, op_j: np.ndarray, j: int, n: int) -> np.ndarray:
    if i == j:
        raise ValueError('sites must be distinct')
    out = np.array([[1.0+0j]])
    for k in range(n):
        if k == i:
            local = op_i
        elif k == j:
            local = op_j
        else:
            local = I2
        out = np.kron(out, local)
    return out


def xyz_dimer_hamiltonian(Jx: float, Jy: float, Jz: float, Dz: float=0.0, h: float=0.0) -> np.ndarray:
    sx,sy,sz = SPIN
    H = (Jx*np.kron(sx,sx) + Jy*np.kron(sy,sy) + Jz*np.kron(sz,sz))
    if Dz:
        H = H + Dz*(np.kron(sx,sy)-np.kron(sy,sx))
    if h:
        H = H - h*(np.kron(sz,I2)+np.kron(I2,sz))
    return H


def chain_hamiltonian(n: int, Jx: float=1.0, Jy: float=1.0, Jz: float=1.0,
                      Dz: float=0.0, h: float=0.0, periodic: bool=False) -> np.ndarray:
    if n < 2:
        raise ValueError('n must be >=2')
    dim = 2**n
    H = np.zeros((dim,dim), dtype=complex)
    sx,sy,sz = SPIN
    bonds = [(i,i+1) for i in range(n-1)]
    if periodic and n > 2:
        bonds.append((n-1,0))
    for i,j in bonds:
        H += Jx*two_site_op(sx,i,sx,j,n)
        H += Jy*two_site_op(sy,i,sy,j,n)
        H += Jz*two_site_op(sz,i,sz,j,n)
        if Dz:
            H += Dz*(two_site_op(sx,i,sy,j,n)-two_site_op(sy,i,sx,j,n))
    if h:
        for i in range(n):
            H -= h*op_on_site(sz,i,n)
    return H


def eigensystem(H: np.ndarray):
    return np.linalg.eigh(H)


def ground_state(H: np.ndarray):
    e,v = np.linalg.eigh(H)
    return float(e[0]), v[:,0]


def spectral_gap(H: np.ndarray, tol: float=1e-10) -> float:
    e = np.linalg.eigvalsh(H)
    e0 = e[0]
    for x in e[1:]:
        if x-e0 > tol:
            return float(x-e0)
    return 0.0


def total_sz_operator(n: int) -> np.ndarray:
    sz = SPIN[2]
    return sum(op_on_site(sz,i,n) for i in range(n))


def magnetization_z(psi: np.ndarray, n: int, per_site: bool=True) -> float:
    v = np.asarray(psi,dtype=complex)
    val = float(np.real(np.vdot(v,total_sz_operator(n)@v)))
    return val/n if per_site else val


def local_magnetizations_z(psi: np.ndarray, n: int) -> np.ndarray:
    sz = SPIN[2]
    return np.array([np.real(np.vdot(psi,op_on_site(sz,i,n)@psi)) for i in range(n)],dtype=float)


def spin_correlation(psi: np.ndarray, i: int, j: int, n: int, component: str='dot') -> float:
    if component == 'dot':
        op = sum(two_site_op(s,i,s,j,n) for s in SPIN)
    elif component == 'xx':
        op = two_site_op(SPIN[0],i,SPIN[0],j,n)
    elif component == 'yy':
        op = two_site_op(SPIN[1],i,SPIN[1],j,n)
    elif component == 'zz':
        op = two_site_op(SPIN[2],i,SPIN[2],j,n)
    else:
        raise ValueError('component must be dot, xx, yy, or zz')
    return float(np.real(np.vdot(psi,op@psi)))


def connected_zz_correlation(psi: np.ndarray, i: int, j: int, n: int) -> float:
    zz = spin_correlation(psi,i,j,n,'zz')
    mz = local_magnetizations_z(psi,n)
    return float(zz-mz[i]*mz[j])


def structure_factor_zz(psi: np.ndarray, n: int, q: float, connected: bool=True) -> float:
    mz = local_magnetizations_z(psi,n)
    total = 0.0+0.0j
    for i in range(n):
        for j in range(n):
            if i == j:
                cij = 0.25 - (mz[i]*mz[j] if connected else 0.0)
            else:
                cij = spin_correlation(psi,i,j,n,'zz')
                if connected:
                    cij -= mz[i]*mz[j]
            total += np.exp(1j*q*(i-j))*cij
    return float(np.real(total)/n)


def magnetization_curve(n: int, fields, **kwargs):
    vals=[]
    for h in fields:
        H=chain_hamiltonian(n,h=float(h),**kwargs)
        _,psi=ground_state(H)
        vals.append(magnetization_z(psi,n,per_site=True))
    return np.array(vals,dtype=float)


def bond_correlations(psi: np.ndarray, n: int, periodic: bool=False) -> np.ndarray:
    bonds=[(i,i+1) for i in range(n-1)]
    if periodic and n>2:
        bonds.append((n-1,0))
    return np.array([spin_correlation(psi,i,j,n,'dot') for i,j in bonds],dtype=float)


def dm_chirality_z(psi: np.ndarray, i: int, j: int, n: int) -> float:
    sx,sy,_=SPIN
    op=two_site_op(sx,i,sy,j,n)-two_site_op(sy,i,sx,j,n)
    return float(np.real(np.vdot(psi,op@psi)))


def reference_summary() -> dict:
    # Dimer XXZ and DM references
    ex_xxz=np.linalg.eigvalsh(xyz_dimer_hamiltonian(1.0,1.0,1.5))
    ex_dm=np.linalg.eigvalsh(xyz_dimer_hamiltonian(1.0,1.0,1.0,Dz=0.4))

    # Open AF Heisenberg chain N=6
    H6=chain_hamiltonian(6,periodic=False)
    e6,psi6=ground_state(H6)
    gap6=spectral_gap(H6)
    nn=spin_correlation(psi6,2,3,6,'dot')
    s_pi=structure_factor_zz(psi6,6,np.pi,connected=True)

    fields=np.array([0.0,0.5,1.0,1.5,2.0,2.5])
    mags=magnetization_curve(6,fields,Jx=1,Jy=1,Jz=1,periodic=False)

    # DM chirality reference on dimer
    ed,psid=ground_state(xyz_dimer_hamiltonian(1,1,1,Dz=0.4))
    chi=dm_chirality_z(psid,0,1,2)
    return {
        'xxz_dimer_eigenvalues': ex_xxz.tolist(),
        'dm_dimer_eigenvalues': ex_dm.tolist(),
        'heisenberg_n6_ground_energy': e6,
        'heisenberg_n6_gap': gap6,
        'heisenberg_n6_middle_bond_dot': nn,
        'heisenberg_n6_structure_factor_pi': s_pi,
        'magnetization_fields': fields.tolist(),
        'magnetization_per_site': mags.tolist(),
        'dm_dimer_ground_energy': ed,
        'dm_dimer_chirality_z': chi,
    }

if __name__=='__main__':
    import json
    print(json.dumps(reference_summary(),indent=2))
