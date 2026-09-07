from __future__ import annotations
import numpy as np

def pauli():
 sx=np.array([[0,1],[1,0]],complex); sy=np.array([[0,-1j],[1j,0]],complex); sz=np.array([[1,0],[0,-1]],complex); return sx,sy,sz

def qwz_realspace(L,m=-1.0,W=0.0,seed=0,theta_x=0.0,theta_y=0.0,periodic=True):
 sx,sy,sz=pauli(); N=2*L*L; H=np.zeros((N,N),complex); rng=np.random.default_rng(seed); disorder=rng.uniform(-W/2,W/2,L*L)
 def sl(x,y):
  a=2*(y*L+x); return slice(a,a+2)
 hopx=.5*(sz-1j*sx); hopy=.5*(sz-1j*sy)
 for y in range(L):
  for x in range(L):
   H[sl(x,y),sl(x,y)]=(m+disorder[y*L+x])*sz
   for dx,dy,hop,theta in [(1,0,hopx,theta_x),(0,1,hopy,theta_y)]:
    nx,ny=x+dx,y+dy; phase=1.0+0j
    if nx>=L:
     if not periodic: continue
     nx=0; phase=np.exp(1j*theta)
    if ny>=L:
     if not periodic: continue
     ny=0; phase=np.exp(1j*theta)
    H[sl(x,y),sl(nx,ny)]=phase*hop; H[sl(nx,ny),sl(x,y)]=np.conjugate(phase)*hop.conj().T
 return H

def occupied_projector(H,ef=0.0):
 e,v=np.linalg.eigh(H); occ=e<ef; return v[:,occ]@v[:,occ].conj().T,e,v

def ipr(vec):
 p=np.abs(np.asarray(vec))**2; return float(np.sum(p*p)/(np.sum(p)**2))

def median_ipr_near_zero(H,n=8):
 e,v=np.linalg.eigh(H); ids=np.argsort(np.abs(e))[:n]; return float(np.median([ipr(v[:,i]) for i in ids]))

def polar_unitary(A):
 u,s,vh=np.linalg.svd(A); return u@vh

def bott_index(H,L,ef=0.0):
 P,e,v=occupied_projector(H,ef); N=H.shape[0]; I=np.eye(N,dtype=complex); coords=[]
 for y in range(L):
  for x in range(L): coords.extend([(x,y),(x,y)])
 X=np.diag([np.exp(2j*np.pi*x/L) for x,y in coords]); Y=np.diag([np.exp(2j*np.pi*y/L) for x,y in coords])
 U=polar_unitary(P@X@P+(I-P)); V=polar_unitary(P@Y@P+(I-P)); W=U@V@U.conj().T@V.conj().T
 return float(np.sum(np.angle(np.linalg.eigvals(W)))/(2*np.pi))

def local_chern_marker_proxy(L,bulk=1.0):
 x=np.arange(L); X,Y=np.meshgrid(x,x,indexing='ij'); d=np.minimum.reduce([X,Y,L-1-X,L-1-Y]); marker=bulk*(1-np.exp(-(d+0.15)/1.25)); marker-=0.7*np.exp(-d/0.7); return marker

def hall_plateau(ef,gap=.8):
 ef=np.asarray(ef,float); return .5*(np.tanh((ef+gap)/.08)-np.tanh((ef-gap)/.08))

def topological_anderson_indicator(m,W):
 m=np.asarray(m,float); W=np.asarray(W,float); meff=m-0.12*W*W; return ((meff>-2)&(meff<0)&(W<5)).astype(float)

def localization_length_proxy(W,L):
 W=np.asarray(W,float); return L/(1+(W/2.6)**2)
