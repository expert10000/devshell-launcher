(* Chapter 43 Wolfram Language companion *)
WrapPhase[x_] := Mod[x + Pi, 2 Pi] - Pi;
SphereLowerCurvature[th_] := Sin[th]/2;
SphereChern := Integrate[SphereLowerCurvature[th], {th, 0, Pi}];
TransitionWinding[n_Integer] := n;
DegreeDensity[th_, n_Integer:1] := n Sin[th]/2;
DegreeNumber[n_Integer:1] := Integrate[DegreeDensity[th,n], {th,0,Pi}];
RegularizedDiracCurvature[kx_,ky_,m_,b_:1] := (m+b(kx^2+ky^2))/(2((kx^2+ky^2)+(m-b(kx^2+ky^2))^2)^(3/2));
RegularizedDiracChern[m_,b_:1] /; m!=0 && b!=0 := (Sign[m]+Sign[b])/2;
HallSigmaYX[c_] := c; HallSigmaXY[c_] := -c; PumpedParticleNumber[c_] := c;
