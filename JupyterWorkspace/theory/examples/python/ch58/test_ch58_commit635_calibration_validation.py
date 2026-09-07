import numpy as np, pytest
from ch58_commit635_calibration_validation import *
def test_identity_fidelity(): assert average_gate_fidelity(I2,I2)==pytest.approx(1)
def test_global_phase(): assert average_gate_fidelity(-I2,I2)==pytest.approx(1)
def test_rotation_unitary():
    U=unitary_rotation((1,2,3),.7); assert np.max(np.abs(U.conj().T@U-I2))<1e-12
def test_zero_axis():
    with pytest.raises(ValueError): unitary_rotation((0,0,0),1)
def test_identity_ptm(): assert np.allclose(pauli_transfer_from_unitary(I2),np.eye(4))
def test_xpi_ptm():
    R=pauli_transfer_from_unitary(unitary_rotation((1,0,0),np.pi)); assert np.allclose(np.diag(R),[1,1,-1,-1],atol=1e-12)
def test_unitarity_one(): assert unitarity_proxy(pauli_transfer_from_unitary(unitary_rotation((0,1,0),.4)))==pytest.approx(1)
def test_choi_identity():
    C=choi_from_kraus([I2]); assert np.trace(C).real==pytest.approx(1); assert np.min(np.linalg.eigvalsh(C))>-1e-12
def test_ad_tp():
    K=amplitude_damping_kraus(.2); assert np.allclose(sum(k.conj().T@k for k in K),I2)
def test_ad_bad():
    with pytest.raises(ValueError): amplitude_damping_kraus(1.2)
def test_cal_shape():
    a,d,F=calibration_fidelity_map(amplitude_errors=np.arange(3),detunings=np.arange(4)); assert F.shape==(4,3)
def test_cal_center():
    a,d,F=calibration_fidelity_map(amplitude_errors=[-.05,0,.05],detunings=[-.1,0,.1]); assert F[1,1]==pytest.approx(F.max())
def test_rb_initial(): assert rb_survival([0],.99,A=.4,B=.5)[0]==pytest.approx(.9)
@pytest.mark.parametrize('p,r',[(1,0),(.99,.005),(.98,.01)])
def test_rb_error(p,r): assert rb_error_per_clifford(p)==pytest.approx(r)
def test_irb_zero(): assert interleaved_rb_gate_error(.995,.995)==pytest.approx(0)
def test_irb_positive(): assert interleaved_rb_gate_error(.995,.985)>0
def test_irb_bad():
    with pytest.raises(ValueError): interleaved_rb_gate_error(0,.9)
def test_leakage_monotone(): assert np.all(np.diff(leakage_rb_survival(np.arange(20),.01))<0)
def test_leakage_zero(): assert np.allclose(leakage_rb_survival(np.arange(5),0),1)
def test_coherent_oscillation():
    y=coherent_overrotation_survival(np.arange(30),.3); assert y.min()<.1 and y.max()>.9
def test_stochastic_damps():
    y=coherent_overrotation_survival(np.arange(100),.2,.98); assert abs(y[-1]-.5)<.1
def test_lowpass_converges(): assert first_order_lowpass(np.ones(200),.9)[-1]>.999999
def test_lowpass_bad():
    with pytest.raises(ValueError): first_order_lowpass(np.ones(3),1)
def test_summary():
    s=robustness_summary([.9,.95,1]); assert s['mean']==pytest.approx(.95) and s['minimum']==pytest.approx(.9)
def test_pareto(): assert pareto_mask([[1,1],[2,2],[.5,3],[3,.5]]).tolist()==[True,False,True,True]
def test_pareto_bad():
    with pytest.raises(ValueError): pareto_mask([1,2])
def test_drift_repro(): assert np.allclose(calibration_drift_trace(seed=4),calibration_drift_trace(seed=4))
def test_drift_nonzero(): assert np.std(calibration_drift_trace(100,.01,3))>0
def test_gate_score(): assert gate_score(.001,.002,20,4,(10,1,0,0))==pytest.approx(.012)
