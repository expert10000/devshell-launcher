from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import hsv_to_rgb

HERE = Path(__file__).resolve().parent
OUT = HERE / "generated"
OUT.mkdir(parents=True, exist_ok=True)
BOOK_OUT = Path(__file__).resolve().parents[3] / "book/parts/part01_mathematical_foundations/chapter05_complex_analysis/figures/generated"
BOOK_OUT.mkdir(parents=True, exist_ok=True)

def save(fig, name):
    for d in (OUT, BOOK_OUT):
        fig.savefig(d / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)

# Domain coloring of z^3-1
x=np.linspace(-1.7,1.7,600); y=np.linspace(-1.4,1.4,500)
X,Y=np.meshgrid(x,y); Z=X+1j*Y; W=Z**3-1
H=(np.angle(W)+np.pi)/(2*np.pi)
V=1-1/(1+np.log1p(np.abs(W)))
S=np.full_like(V,0.85)
RGB=hsv_to_rgb(np.dstack((H,S,np.clip(0.25+0.75*V,0,1))))
fig,ax=plt.subplots(figsize=(7.4,5.0)); ax.imshow(RGB,extent=[x.min(),x.max(),y.min(),y.max()],origin='lower',aspect='equal'); ax.set_xlabel('Re z'); ax.set_ylabel('Im z'); ax.set_title(r'Domain coloring of $f(z)=z^3-1$'); save(fig,'domain_coloring')

# roots
n=8; roots=np.exp(2j*np.pi*np.arange(n)/n)
fig,ax=plt.subplots(figsize=(5.6,5.6)); t=np.linspace(0,2*np.pi,500); ax.plot(np.cos(t),np.sin(t)); ax.plot(np.r_[roots.real,roots.real[0]],np.r_[roots.imag,roots.imag[0]],'o-'); ax.axhline(0,linewidth=.7); ax.axvline(0,linewidth=.7); ax.set_aspect('equal'); ax.set_xlabel('Re z'); ax.set_ylabel('Im z'); ax.set_title('Eighth roots of unity'); save(fig,'roots_of_unity')
print('max root residual',np.max(np.abs(roots**n-1)))

# square map side by side
fig,axs=plt.subplots(1,2,figsize=(9.2,4.1))
vals=np.linspace(-1.3,1.3,11); t=np.linspace(-1.3,1.3,350)
for c in vals:
    z=t+1j*c; axs[0].plot(z.real,z.imag,linewidth=.7); w=z**2; axs[1].plot(w.real,w.imag,linewidth=.7)
    z=c+1j*t; axs[0].plot(z.real,z.imag,linewidth=.7); w=z**2; axs[1].plot(w.real,w.imag,linewidth=.7)
axs[0].set_title('$z$-plane grid'); axs[1].set_title('image under $w=z^2$')
for ax in axs: ax.set_aspect('equal'); ax.set_xlabel('real'); ax.set_ylabel('imaginary')
save(fig,'square_mapping')

# contour convergence
def trap_contour(n):
    t=np.linspace(0,2*np.pi,n+1); z=np.exp(1j*t); f=1/z
    return np.sum(0.5*(f[:-1]+f[1:])*(z[1:]-z[:-1]))
ns=2**np.arange(3,12); errs=np.array([abs(trap_contour(int(n))-2j*np.pi) for n in ns])
fig,ax=plt.subplots(figsize=(6.6,4.5)); ax.loglog(ns,errs,'o-'); ax.set_xlabel('number of panels'); ax.set_ylabel(r'$|I_N-2\pi i|$'); ax.set_title(r'Convergence for $\oint dz/z$'); ax.grid(True,which='both',linewidth=.4); save(fig,'contour_convergence')
print('finest contour value',trap_contour(int(ns[-1])))
print('finest error',errs[-1])
