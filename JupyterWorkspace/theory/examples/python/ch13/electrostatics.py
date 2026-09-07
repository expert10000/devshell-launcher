"""Deterministic electrostatics companion for Chapter 13."""
from __future__ import annotations
import numpy as np
K=1.0

def point_potential(points, charges, positions, softening=0.0):
    p=np.asarray(points,float); q=np.asarray(charges,float); x=np.asarray(positions,float)
    d=p[...,None,:]-x
    r=np.sqrt(np.sum(d*d,axis=-1)+softening**2)
    return K*np.sum(q/r,axis=-1)

def point_field(points, charges, positions, softening=0.0):
    p=np.asarray(points,float); q=np.asarray(charges,float); x=np.asarray(positions,float)
    d=p[...,None,:]-x
    r2=np.sum(d*d,axis=-1)+softening**2
    return K*np.sum(q*d/(r2[...,None]**1.5),axis=-2)

def ring_axis_potential(z,a=1.0,Q=1.0,n=400):
    th=np.linspace(0,2*np.pi,n,endpoint=False)
    src=np.c_[a*np.cos(th),a*np.sin(th),np.zeros_like(th)]
    pts=np.c_[np.zeros_like(z),np.zeros_like(z),z]
    return point_potential(pts,np.full(n,Q/n),src)

def ring_axis_exact(z,a=1.0,Q=1.0): return K*Q/np.sqrt(np.asarray(z)**2+a*a)

def dipole_exact(points,d=.4):
    return point_potential(points,[1,-1],[[d/2,0],[-d/2,0]])

def dipole_approx(points,d=.4):
    p=np.asarray(points,float); r=np.linalg.norm(p,axis=-1)
    return K*d*p[...,0]/r**3

def laplacian5(v,h):
    return (v[2:,1:-1]+v[:-2,1:-1]+v[1:-1,2:]+v[1:-1,:-2]-4*v[1:-1,1:-1])/h**2

def solve_poisson(rho,h,omega=1.8,tol=1e-7,max_iter=20000):
    v=np.zeros_like(rho,float); hist=[]
    for it in range(max_iter):
        for parity in (0,1):
            for i in range(1,v.shape[0]-1):
                js=np.arange(1,v.shape[1]-1); js=js[(i+js)%2==parity]
                new=.25*(v[i+1,js]+v[i-1,js]+v[i,js+1]+v[i,js-1]+h*h*rho[i,js])
                v[i,js]=(1-omega)*v[i,js]+omega*new
        if it%20==0:
            res=np.max(np.abs(laplacian5(v,h)+rho[1:-1,1:-1])); hist.append(res)
            if res<tol: break
    return v,np.asarray(hist)

def gradient_field(v,h):
    ey,ex=np.gradient(-v,h,h)
    return ex,ey

def field_energy(ex,ey,h): return .5*np.sum(ex*ex+ey*ey)*h*h
