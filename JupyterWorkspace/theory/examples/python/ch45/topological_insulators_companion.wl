(* Chapter 45 Wolfram Language companion *)
ClearAll[TrimMass, ParityDelta, Z2Parity, FiniteSizeGap, PenetrationDepth, SurfaceDiracEnergy, ThetaAngle, SurfaceHall];
TrimMass[kx_, ky_, m_] := m + Cos[kx] + Cos[ky];
ParityDelta[kx_, ky_, m_] := -Sign[TrimMass[kx, ky, m]];
Z2Parity[m_] := Mod[If[Times @@ (ParityDelta @@@ {{0,0,m},{Pi,0,m},{0,Pi,m},{Pi,Pi,m}}) == -1, 1, 0], 2];
FiniteSizeGap[w_, xi_, g0_:1] := 2 g0 Exp[-w/xi];
PenetrationDepth[m_, hv_:1] := hv/Abs[m];
SurfaceDiracEnergy[kx_, ky_, v_:1, mass_:0] := Sqrt[v^2 (kx^2+ky^2)+mass^2];
ThetaAngle[nu0_] := Pi nu0;
SurfaceHall[dtheta_] := dtheta/(2 Pi); (* units e^2/h *)
