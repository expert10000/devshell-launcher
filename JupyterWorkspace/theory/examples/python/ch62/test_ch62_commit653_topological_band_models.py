import numpy as np
from topological_band_models import *
def test_ssh_gap_closes(): assert np.isclose(ssh_bulk_gap(1,1),0)
def test_ssh_hermitian():
 H=ssh_bloch(.3,.7,1); assert np.allclose(H,H.conj().T)
def test_open_ssh_hermitian(): 
 H=ssh_open_hamiltonian(8,.5,1); assert np.allclose(H,H.T)
def test_topological_edge_mode_small():
 e=np.linalg.eigvalsh(ssh_open_hamiltonian(24,.4,1)); assert np.min(np.abs(e))<1e-7
def test_rice_mele_cycle_closed():
 s,d,m,q=rice_mele_loop(); assert np.allclose([d[0],m[0]],[d[-1],m[-1]]) and np.isclose(q[-1],1)
def test_qwz_hermitian():
 H=qwz_bloch(.2,.4,-1); assert np.allclose(H,H.conj().T)
def test_lattice_chern_quantized():
 assert abs(lattice_chern(-1,n=25)+1)<.05
def test_trivial_chern():
 assert abs(lattice_chern(3,n=25))<.05
def test_ribbon_hermitian():
 H=qwz_ribbon(8,.4,-1); assert np.allclose(H,H.conj().T)
