(* Chapter 42 Berry geometry computational companion *)
ClearAll[SolidAngleCone, SpinHalfBerryPhase, MassiveDiracCurvature, PolarizationFromZak,
  PumpedChargeFromChern, QuantumMetricSphere, BerryCurvatureSphere];
SolidAngleCone[theta_] := 2 Pi (1 - Cos[theta]);
SpinHalfBerryPhase[theta_, branch_: 1] := -branch SolidAngleCone[theta]/2;
MassiveDiracCurvature[kx_, ky_, m_, branch_: -1] := -branch m/(2 (kx^2 + ky^2 + m^2)^(3/2));
PolarizationFromZak[gamma_, e_: 1] := -e gamma/(2 Pi);
PumpedChargeFromChern[c_Integer, e_: 1] := e c;
QuantumMetricSphere[theta_] := {{1/4, 0}, {0, Sin[theta]^2/4}};
BerryCurvatureSphere[theta_, branch_: -1] := -branch Sin[theta]/2;
