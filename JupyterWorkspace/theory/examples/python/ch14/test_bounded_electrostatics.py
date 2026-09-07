import numpy as np
from bounded_electrostatics import *


def test_nodal_matrix_symmetric():
    p=np.array([[0,2,1],[2,0,3],[1,3,0]],float); g=np.array([1,2,4],float)
    assert np.allclose(nodal_capacitance(p,g),nodal_capacitance(p,g).T)


def test_nodal_matrix_positive_energy():
    p=np.array([[0,1],[1,0]],float); c=nodal_capacitance(p,np.array([2,3]))
    assert electrostatic_energy(c,np.array([1.2,-.4]))>0


def test_floating_guard_divider():
    p=np.array([[0,3],[3,0]],float); c=nodal_capacitance(p,np.array([1,2]))
    v=solve_floating(c,np.array([0,np.nan]),np.array([1]),np.array([4.0]))
    assert np.isclose(v[0],3.0)


def test_coax_homogeneous_limit():
    assert np.isclose(coax_two_layer_capacitance(1,2,4,5,5),2*np.pi*5/np.log(4))


def test_sphere_homogeneous_limit():
    assert np.isclose(spherical_two_layer_capacitance(1,2,4,3,3),4*np.pi*3/(1-1/4))


def test_layered_plate_homogeneous_limit():
    assert np.isclose(layered_parallel_plate_capacitance(2,[.2,.3],[4,4]),2*4/.5)


def test_layered_potential_endpoints():
    z=np.array([0,.3,.8]); v=layered_potential(z,[.3,.5],[2,5],7)
    assert np.isclose(v[0],7) and np.isclose(v[-1],0)


def test_displacement_continuity():
    voltage=6; t=np.array([.2,.4]); e=np.array([2.,5.])
    d=voltage/np.sum(t/e); assert np.isclose(e[0]*(d/e[0]),e[1]*(d/e[1]))


def test_image_plane_boundary_zero():
    x=np.linspace(-3,3,41); assert np.max(np.abs(image_plane_potential(x,0*x,height=1.2)))<1e-13


def test_image_sphere_boundary_zero():
    th=np.linspace(0,np.pi,100); assert np.max(np.abs(image_sphere_potential(1+0*th,th,a=1,d=2.4)))<1e-12


def test_rectangle_boundary_mode():
    x=np.linspace(0,1,51); y=np.ones_like(x)
    assert np.max(np.abs(rectangle_laplace(x,y)-np.sin(np.pi*x)))<1e-12


def test_discrete_laplacian_quadratic():
    x=np.linspace(-1,1,41); h=x[1]-x[0]; X,Y=np.meshgrid(x,x)
    assert np.max(np.abs(laplacian5(X*X-Y*Y,h)))<1e-10


def test_sor_residual():
    n=51; h=1/(n-1); b=np.full((n,n),np.nan); b[0,:]=0; b[-1,:]=np.sin(np.pi*np.linspace(0,1,n)); b[:,0]=0; b[:,-1]=0
    _,hist=solve_laplace_dirichlet(b,h,tol=2e-7)
    assert hist[-1]<5e-7


def test_pull_in_scaling():
    v1=pull_in_voltage(2,1,3,4); v2=pull_in_voltage(8,1,3,4)
    assert np.isclose(v2/v1,2)
