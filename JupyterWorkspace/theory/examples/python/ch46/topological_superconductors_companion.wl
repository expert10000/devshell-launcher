(* Chapter 46 Topological Superconductors computational companion *)
ClearAll[UniformBdGEnergy, KitaevEnergy, KitaevZ2, MajoranaEnvelope, MajoranaSplitting,
  NanowireCriticalZeeman, NanowireTopologicalQ, ChiralMajoranaThermalUnit, JosephsonMajoranaEnergy];
UniformBdGEnergy[xi_, delta_] := Sqrt[xi^2 + Abs[delta]^2];
KitaevEnergy[k_, mu_, t_:1, delta_:1] := Sqrt[(-2 t Cos[k]-mu)^2 + (2 delta Sin[k])^2];
KitaevZ2[mu_, t_:1] := Which[Abs[mu] < 2 Abs[t], 1, Abs[mu] > 2 Abs[t], 0, True, Indeterminate];
MajoranaEnvelope[x_, xi_:5] := Exp[-Abs[x]/xi];
MajoranaSplitting[L_, xi_:5, kf_:.7, phase_:0, amp_:1] := amp Exp[-L/xi] Cos[kf L + phase];
NanowireCriticalZeeman[mu_, delta_] := Sqrt[mu^2 + delta^2];
NanowireTopologicalQ[vz_, mu_, delta_] := Abs[vz] > NanowireCriticalZeeman[mu,delta];
ChiralMajoranaThermalUnit[C_] := C;
JosephsonMajoranaEnergy[phi_, em_:1, parity_:1] := parity em Cos[phi/2];
