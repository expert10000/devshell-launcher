(* Chapter 48 Quantum Geometry and Modern Hall Physics companion *)
ClearAll[TwoLevelLowerGeometry, MetricDeterminant, DeterminantBoundMargin,
  TraceBoundMargin, IntegratedMetricLowerBound, LandauFormFactor,
  GMPCoefficient, NormalizedRMSFluctuation, FCIProjectionHierarchy,
  FractionalHallResponse, MeanOrbitalSpin, HallViscosity, SphereFlux,
  WenZeeParticleNumber, GuidingCenterSpin, StructureFactorS4Bound];
TwoLevelLowerGeometry[kx_,ky_,m_] := Module[{r2=kx^2+ky^2+m^2},
  {(ky^2+m^2)/(4 r2^2),(kx^2+m^2)/(4 r2^2),-kx ky/(4 r2^2),-m/(2 r2^(3/2))}];
MetricDeterminant[gxx_,gyy_,gxy_] := gxx gyy-gxy^2;
DeterminantBoundMargin[gxx_,gyy_,gxy_,f_] := MetricDeterminant[gxx,gyy,gxy]-f^2/4;
TraceBoundMargin[gxx_,gyy_,f_] := gxx+gyy-Abs[f];
IntegratedMetricLowerBound[c_] := 2 Pi Abs[c];
LandauFormFactor[n_Integer?NonNegative,q_,ell_:1] := Exp[-(q ell)^2/4] LaguerreL[n,(q ell)^2/2];
GMPCoefficient[q_,qp_,ell_:1] := 2 Sin[ell^2 Det[{q,qp}]/2];
NormalizedRMSFluctuation[x_List] := Sqrt[Mean[(x-Mean[x])^2]]/Abs[Mean[x]];
FCIProjectionHierarchy[w_,u_,gap_,tol_:.2] := {w/u,u/gap,w/u<tol && u/gap<tol};
FractionalHallResponse[c_,deg_Integer?Positive] := c/deg;
MeanOrbitalSpin[shift_] := shift/2;
HallViscosity[rho_,shift_,hbar_:1] := hbar rho shift/4;
SphereFlux[n_,nu_,shift_] := n/nu-shift;
WenZeeParticleNumber[nu_,flux_,shift_,chi_:2] := nu flux+nu shift chi/2;
GuidingCenterSpin[shift_] := (1-shift)/2;
StructureFactorS4Bound[shift_] := Abs[GuidingCenterSpin[shift]]/4;
