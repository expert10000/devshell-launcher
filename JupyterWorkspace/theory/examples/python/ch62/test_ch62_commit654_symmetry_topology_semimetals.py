import numpy as np
from symmetry_topology_semimetals import *
def test_dirac_gap(): assert np.isclose(dirac_energy(0,.7),.7)
def test_qsh_window():
 x=qsh_topological(np.array([-1.,1.,5.])); assert np.array_equal(x,[False,True,False])
def test_helical_kramers_crossing():
 k=np.array([0.]); up,dn,bp,bm=qsh_edge_spectrum(k); assert np.isclose(up[0],dn[0])
def test_wilson_partner_symmetry():
 k=np.linspace(0,1,20); a,b=wilson_helical_flow(k); assert np.all((a>=0)&(a<2*np.pi)) and np.all((b>=0)&(b<2*np.pi))
def test_weyl_zero_at_node(): assert np.isclose(weyl_energy(0,0,0),0)
def test_weyl_chirality_sign(): assert weyl_chirality((1,1,-1))==-1
def test_nodal_ring_zero(): assert np.isclose(nodal_ring_energy(1,0,0),0)
def test_nodal_ring_gapped_off_plane(): assert nodal_ring_energy(1,0,.2)>0
