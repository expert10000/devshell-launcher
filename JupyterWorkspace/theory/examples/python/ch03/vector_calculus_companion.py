#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[3] / "generated" / "ch03"
OUT.mkdir(parents=True, exist_ok=True)

x = np.linspace(-2, 2, 25)
y = np.linspace(-2, 2, 25)
X, Y = np.meshgrid(x, y)
Fx, Fy = -Y, X

fig, ax = plt.subplots(figsize=(6, 5))
ax.quiver(X, Y, Fx, Fy)
ax.set_aspect("equal")
ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_title("Rotational field F=(-y,x)")
fig.tight_layout(); fig.savefig(OUT / "rotational_field.pdf"); plt.close(fig)

dx=x[1]-x[0]; dy=y[1]-y[0]
curl=np.gradient(Fy, dx, axis=1)-np.gradient(Fx, dy, axis=0)
fig, ax = plt.subplots(figsize=(6, 5))
im=ax.imshow(curl, extent=[x.min(),x.max(),y.min(),y.max()], origin="lower")
fig.colorbar(im, ax=ax, label="scalar curl")
ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_title("Numerical curl")
fig.tight_layout(); fig.savefig(OUT / "curl_map.pdf"); plt.close(fig)

t=np.linspace(0,2*np.pi,300)
R=1.5
xc,yc=R*np.cos(t),R*np.sin(t)
fig,ax=plt.subplots(figsize=(6,5))
ax.plot(xc,yc)
sel=np.arange(0,len(t),24)
ax.quiver(xc[sel],yc[sel],xc[sel],yc[sel],angles="xy",scale_units="xy",scale=3)
ax.set_aspect("equal"); ax.set_xlabel("x"); ax.set_ylabel("y")
ax.set_title("Outward flux through a circular boundary")
fig.tight_layout(); fig.savefig(OUT / "flux_circle.pdf"); plt.close(fig)

xx=np.linspace(-np.pi,np.pi,500)
fig,ax=plt.subplots(figsize=(6,5))
for time in (0.0,0.15,0.5,1.0):
    u=np.exp(-4*time)*np.cos(2*xx)
    ax.plot(xx,u,label=f"t={time:g}")
ax.set_xlabel("x"); ax.set_ylabel("u(x,t)"); ax.set_title("Diffusion damps high-curvature modes")
ax.legend(); fig.tight_layout(); fig.savefig(OUT / "diffusion_modes.pdf"); plt.close(fig)

# Numerical diagnostics
print(f"mean curl = {curl.mean():.8f} (analytic value 2)")
# circulation of (-y,x) around radius R
circ=np.trapz(R**2*np.ones_like(t),t)
print(f"circle circulation = {circ:.8f}; analytic = {2*np.pi*R**2:.8f}")
