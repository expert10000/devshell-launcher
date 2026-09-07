import math
import numpy as np

from magnetostatics_companion import (
    MU0, apparent_susceptibility, curl_z, dipole_axis_field,
    gapped_core_flux_density, hysteresis_branches, hysteresis_loop_area,
    landau_gauge, loop_axis_field, manufactured_solution, max_error,
    poisson_residual, solenoid_axis_field, solve_poisson_dirichlet,
    symmetric_gauge,
)


def test_loop_center_field():
    a=0.23; i=1.7
    assert math.isclose(float(loop_axis_field(0.0,a,i)), MU0*i/(2*a), rel_tol=1e-13)


def test_loop_far_field_matches_dipole():
    a=0.2; i=2.0; z=20*a; moment=i*math.pi*a*a
    rel=abs(float(loop_axis_field(z,a,i)/dipole_axis_field(z,moment)-1))
    assert rel < 0.004


def test_long_solenoid_center_limit():
    r=.02; length=1.0; turns=2000; i=.4
    exact=float(solenoid_axis_field(0,r,length,turns,i))
    ideal=MU0*(turns/length)*i
    assert abs(exact/ideal-1)<0.001


def test_symmetric_gauge_curl():
    x=np.linspace(-1,1,41); xx,yy=np.meshgrid(x,x); b=.73
    ax,ay=symmetric_gauge(xx,yy,b)
    assert np.max(abs(curl_z(ax,ay,x[1]-x[0])-b))<1e-12


def test_landau_gauge_curl():
    x=np.linspace(-1,1,41); xx,yy=np.meshgrid(x,x); b=.73
    ax,ay=landau_gauge(xx,yy,b)
    assert np.max(abs(curl_z(ax,ay,x[1]-x[0])-b))<1e-12


def test_gauge_difference_is_gradient_of_bxy_over_two():
    x=np.linspace(-1,1,41); xx,yy=np.meshgrid(x,x); b=.73; h=x[1]-x[0]
    axs,ays=symmetric_gauge(xx,yy,b); axl,ayl=landau_gauge(xx,yy,b)
    chi=.5*b*xx*yy
    dchi_dx=np.gradient(chi,h,axis=1,edge_order=2)
    dchi_dy=np.gradient(chi,h,axis=0,edge_order=2)
    assert np.max(abs((axl-axs)-dchi_dx))<1e-12
    assert np.max(abs((ayl-ays)-dchi_dy))<1e-12


def test_sphere_apparent_susceptibility_limit():
    assert abs(float(apparent_susceptibility(1e9,1/3))-3.0)<1e-7


def test_zero_demag_preserves_susceptibility():
    vals=np.array([-.01,.1,5.0])
    assert np.allclose(apparent_susceptibility(vals,0),vals)


def test_hysteresis_area_positive():
    assert hysteresis_loop_area()>0


def test_hysteresis_remanence_has_opposite_branches():
    up,down=hysteresis_branches(np.array([0.0]))
    assert up[0]<0<down[0]


def test_gapless_core_limit():
    i=.3; n=400; ell=.2; mur=1000
    b=float(gapped_core_flux_density(i,n,ell,mur,0))
    assert math.isclose(b,MU0*mur*n*i/ell,rel_tol=1e-13)


def test_gap_reduces_flux_density():
    gaps=np.array([0,1e-4,1e-3])
    b=gapped_core_flux_density(.3,400,.2,1000,gaps)
    assert np.all(np.diff(b)<0)


def test_poisson_residual_converges():
    exact,source,_=manufactured_solution(41)
    result=solve_poisson_dirichlet(source,tolerance=5e-7)
    residual=poisson_residual(result.potential,source,result.spacing)
    assert np.max(abs(residual[1:-1,1:-1]))<6e-7
    assert max_error(result.potential,exact)<7e-4


def test_second_order_grid_convergence():
    errs=[]
    for n in (21,41):
        exact,source,_=manufactured_solution(n)
        result=solve_poisson_dirichlet(source,tolerance=2e-7)
        errs.append(max_error(result.potential,exact))
    assert errs[0]/errs[1]>3.5
