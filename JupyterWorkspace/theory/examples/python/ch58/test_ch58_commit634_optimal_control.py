import numpy as np, pytest
from ch58_commit634_optimal_control import *

def test_gaussian_area():
 t=np.linspace(-4,4,2001); p=gaussian_envelope(t,.7,np.pi); assert pulse_area(t,p)==pytest.approx(np.pi,rel=1e-8)
def test_gaussian_symmetry():
 t=np.linspace(-3,3,1001); p=gaussian_envelope(t,.6); assert np.max(abs(p-p[::-1]))<1e-12
def test_gaussian_width_validation():
 with pytest.raises(ValueError): gaussian_envelope(np.linspace(0,1,10),0)
def test_drag_zero_area():
 t=np.linspace(-4,4,2001); I=gaussian_envelope(t,.7); assert abs(pulse_area(t,drag_quadrature(t,I,-5)))<1e-8
def test_drag_antisymmetric():
 t=np.linspace(-3,3,1001); I=gaussian_envelope(t,.6); Q=drag_quadrature(t,I,-4); assert np.max(abs(Q+Q[::-1]))<1e-10
def test_rot_frame_hermitian():
 H=rotating_frame_hamiltonian(.2,.7,-.3); assert np.max(abs(H-H.conj().T))<1e-14
def test_unitary_step():
 U=hermitian_step(rotating_frame_hamiltonian(.2,.7,-.3),.05); assert np.max(abs(U.conj().T@U-I2))<1e-12
def test_qutrit_norm():
 t=np.linspace(-3,3,601); psi=qutrit_propagate(t,gaussian_envelope(t,.7),anharmonicity=-4); assert np.linalg.norm(psi)==pytest.approx(1,rel=1e-10)
def test_leakage_readout():
 psi=np.array([np.sqrt(.8),np.sqrt(.1),np.sqrt(.1)],complex); assert leakage_probability(psi)==pytest.approx(.1)
def test_population_readout():
 psi=np.array([0,np.sqrt(.7),np.sqrt(.3)],complex); assert state_population(psi,1)==pytest.approx(.7)
def test_drag_reduces_leakage():
 b=gaussian_pi_benchmark(-4,beta=1); assert b['drag_leakage']<.1*b['plain_leakage']
def test_plain_pi_populates_one():
 b=gaussian_pi_benchmark(-4,beta=1); assert state_population(b['plain_state'],1)>.90
def test_spectrum_nonnegative():
 t=np.linspace(-3,3,1001); w,s=pulse_spectrum(t,gaussian_envelope(t,.7)); assert np.all(w>=0) and np.all(s>=0)
def test_avg_fidelity_identity(): assert average_gate_fidelity(I2,I2)==pytest.approx(1)
def test_avg_fidelity_global_phase(): assert average_gate_fidelity(-I2,I2)==pytest.approx(1)
def test_grape_exact_x():
 n=40; dt=np.pi/n; u=np.zeros((n,2)); u[:,0]=1; target=hermitian_step(.5*SX,np.pi); F,g,U=grape_fidelity_and_gradient(u,dt,target); assert F>1-1e-12 and average_gate_fidelity(U,target)>1-1e-12 and g.shape==u.shape
def test_grape_gradient_fd():
 rng=np.random.default_rng(4); u=.2*rng.standard_normal((20,2)); dt=.02; target=hermitian_step(.5*SX,.7); F,g,_=grape_fidelity_and_gradient(u,dt,target); eps=1e-6; u2=u.copy(); u2[7,1]+=eps; F2,_,_=grape_fidelity_and_gradient(u2,dt,target); assert g[7,1]==pytest.approx((F2-F)/eps,rel=2e-2,abs=2e-4)
def test_grape_optimization_improves():
 rng=np.random.default_rng(2); n=40; u=.05*rng.standard_normal((n,2)); target=hermitian_step(.5*SX,np.pi); _,h,_=optimize_grape(u,np.pi/n,target,60,5); assert h[-1]>h[0]+.8 and h[-1]>.95
def test_grape_bound():
 u=np.zeros((20,2)); target=hermitian_step(.5*SX,np.pi); u,_,_=optimize_grape(u,np.pi/20,target,20,5,1.2); assert np.max(abs(u))<=1.2+1e-12
def test_filter_zero():
 t=np.linspace(0,1,401); w=np.linspace(0,20,101); assert np.max(switching_filter(t,np.zeros_like(t),w))==pytest.approx(0)
def test_filter_dc_constant():
 t=np.linspace(0,2,1001); assert switching_filter(t,np.ones_like(t),np.array([0.]))[0]==pytest.approx(4,rel=1e-6)
def test_overlap_nonnegative():
 t=np.linspace(0,1,401); w=np.linspace(0,30,301); S=1/(1+w*w); assert spectral_overlap(t,np.ones_like(t),w,S)>=0
@pytest.mark.parametrize('p,expected',[(1.,0.),(.99,.005),(.98,.01)])
def test_rb_conversion(p,expected): assert rb_error_per_clifford(p,2)==pytest.approx(expected)
def test_rb_start():
 y=rb_survival(np.array([0,1,2]),.99,.4,.5); assert y[0]==pytest.approx(.9)
def test_rb_decay():
 y=rb_survival(np.arange(10),.99); assert np.all(np.diff(y)<0)
def test_large_anharmonicity_reduces_leakage():
 t=np.linspace(-3,3,801); I=gaussian_envelope(t,.7); assert leakage_probability(qutrit_propagate(t,I,anharmonicity=-10))<leakage_probability(qutrit_propagate(t,I,anharmonicity=-3))
def test_zero_beta():
 t=np.linspace(-2,2,401); I=gaussian_envelope(t,.5); assert np.max(abs(drag_quadrature(t,I,-4,0)))==pytest.approx(0)
def test_bad_grape_shape():
 with pytest.raises(ValueError): grape_fidelity_and_gradient(np.zeros((10,3)),.1,I2)
def test_bad_rb_dimension():
 with pytest.raises(ValueError): rb_error_per_clifford(.99,1)
