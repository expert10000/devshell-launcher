(* Wolfram Language companion for Chapter 44 -- Haldane model and Chern diagnostics. *)
ClearAll[ValleyMasses, ChernFromMasses, EdgeDispersion, PenetrationDepth, FiniteWidthGap,
  HallSigmaYX, HallSigmaXY, DomainWallProbability];
ValleyMasses[M_, t2_, phi_] := {M - 3 Sqrt[3] t2 Sin[phi], M + 3 Sqrt[3] t2 Sin[phi]};
ChernFromMasses[M_, t2_, phi_] := Module[{m = ValleyMasses[M, t2, phi]},
  If[MemberQ[Sign[m], 0], Indeterminate, (Sign[m[[2]]] - Sign[m[[1]]])/2]];
EdgeDispersion[k_, v_: 1, chirality_: 1] := chirality v k;
PenetrationDepth[m_, hbarv_: 1] := If[m == 0, Infinity, Abs[hbarv/m]];
FiniteWidthGap[W_, xi_, gap0_: 1] := 2 gap0 Exp[-W/xi];
HallSigmaYX[C_] := C;
HallSigmaXY[C_] := -C;
DomainWallProbability[y_, m0_: 1, lambda_: 1, hbarv_: 1] :=
  Cosh[y/lambda]^(-2 Abs[m0] lambda/hbarv);
(* The Python companion supplies the full reciprocal-lattice Haldane solver and Fukui mesh tests. *)
