(* Chapter 47 Anyons and Topological Quantum Computation companion *)
ClearAll[GoldenRatioQ, FibonacciFusionDims, FibonacciF, FibonacciR, FibonacciBraids,
  ProjectiveDistance, ForcedSuccessProbability, ExpectedForcedAttempts,
  MagicStatePhaseFidelity, LeakageSurvival, PoisoningProbability, AdiabaticWindow];
GoldenRatioQ[] := (1 + Sqrt[5])/2;
FibonacciFusionDims[n_Integer?Positive] := Nest[{#[[2]], Total[#]} &, {0,1}, n-1];
FibonacciF[] := With[{ph=GoldenRatioQ[]}, {{1/ph,1/Sqrt[ph]},{1/Sqrt[ph],-1/ph}}];
FibonacciR[] := DiagonalMatrix[{Exp[-4 Pi I/5],Exp[3 Pi I/5]}];
FibonacciBraids[] := Module[{f=FibonacciF[],b1=FibonacciR[]}, {b1, ConjugateTranspose[f].b1.f}];
ProjectiveDistance[u_,v_] := Sqrt[Max[0,1-Abs[Tr[ConjugateTranspose[u].v]]/Length[u]]];
ForcedSuccessProbability[p_,n_Integer?NonNegative] := 1-(1-p)^n;
ExpectedForcedAttempts[p_] := 1/p;
MagicStatePhaseFidelity[delta_] := Cos[delta/2]^2;
LeakageSurvival[p_,n_Integer?NonNegative] := (1-p)^n;
PoisoningProbability[t_,tau_] := 1-Exp[-t/tau];
AdiabaticWindow[split_,gap_,hbar_:1] := {hbar/gap, If[split==0,Infinity,hbar/split], split<gap};
