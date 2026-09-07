import numpy as np
from geometric_topology_launch import *
def test_solid_angle_linear():
    o=np.array([0.,1.,2.]); g=berry_phase_solid_angle(o,-1); assert np.allclose(np.diff(g),.5)
def test_curvature_positive(): assert np.all(two_level_curvature_magnitude(np.array([0.,1.]),np.array([0.,1.]))>0)
def test_parameter_loop_closed():
    x,y,z=parameter_loop(.2); assert np.allclose([x[0],y[0]],[x[-1],y[-1]])
def test_chern_converges():
    n,c=accumulated_chern_flux(); assert c[-1]>c[0] and abs(c[-1]-1)<.001
def test_pump_ends_one():
    t,d,m,q=thouless_cycle(); assert np.isclose(q[0],0) and np.isclose(q[-1],1)
def test_metric_nonnegative():
    assert np.all(quantum_metric_two_level(np.linspace(0,np.pi,20))>=0)
