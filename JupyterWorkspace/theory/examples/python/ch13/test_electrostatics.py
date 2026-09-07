import numpy as np
from electrostatics import *
def test_point_potential_inverse_r(): assert np.isclose(point_potential([[2,0]],[1],[[0,0]])[0],.5)
def test_point_field_inverse_square(): assert np.allclose(point_field([[2,0]],[1],[[0,0]])[0],[.25,0])
def test_superposition_scalar(): assert np.isclose(point_potential([[0,2]],[1,1],[[-1,0],[1,0]])[0],2/np.sqrt(5))
def test_dipole_midplane_zero(): assert abs(dipole_exact([[0,2]])[0])<1e-14
def test_ring_exact_center(): assert np.isclose(ring_axis_exact(np.array([0.]))[0],1.)
def test_ring_discrete_center(): assert np.isclose(ring_axis_potential(np.array([0.]),n=32)[0],1.)
def test_ring_convergence():
 z=np.array([.3,1.]); assert np.max(abs(ring_axis_potential(z,n=24)-ring_axis_exact(z)))<1e-12
def test_dipole_far_accuracy():
 p=np.array([[20*np.cos(.4),20*np.sin(.4)]]); assert abs((dipole_approx(p)-dipole_exact(p))[0]/dipole_exact(p)[0])<1e-3
def test_laplacian_quadratic():
 n=31; x=np.linspace(-1,1,n); h=x[1]-x[0]; X,Y=np.meshgrid(x,x); assert np.max(abs(laplacian5(X*X+Y*Y,h)-4))<1e-10
def test_poisson_residual():
 n=31; h=2/(n-1); rho=np.zeros((n,n)); rho[n//2,n//2]=1; v,hist=solve_poisson(rho,h,tol=1e-5); assert hist[-1]<2e-5
def test_gradient_linear_potential():
 n=31; x=np.linspace(-1,1,n); h=x[1]-x[0]; X,Y=np.meshgrid(x,x); ex,ey=gradient_field(3*X-2*Y,h); assert np.allclose(ex[2:-2,2:-2],-3) and np.allclose(ey[2:-2,2:-2],2)
def test_energy_positive():
 a=np.ones((5,5)); assert field_energy(a,2*a,.1)>0
def test_energy_zero_field(): assert field_energy(np.zeros((4,4)),np.zeros((4,4)),.2)==0
def test_force_direction_positive_charge(): assert point_field([[1,0]],[1],[[0,0]])[0,0]>0
