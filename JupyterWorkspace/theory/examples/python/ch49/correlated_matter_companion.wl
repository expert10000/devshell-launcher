(* Chapter 49 Topological and Strongly Correlated Matter companion *)
ClearAll[CriticalScalingVariable, CorrectionAwareObservable, LinearRGFlow,
  ClassifyRGDirection, GreenZeroFromHamiltonian, TopologicalHamiltonianFromGreen,
  Z2WilsonLoop, AreaLawWilson, NonFermiSelfEnergy, OmegaTVariable,
  OmegaTResponse, PlanckianRate, NodalGap, DiracDOS, MoireLength,
  MoireProjectionHierarchy, FloquetPrethermalTime];
CriticalScalingVariable[delta_,L_,nu_] := delta L^(1/nu);
CorrectionAwareObservable[delta_,L_,nu_,omega_,a_:.2] := Tanh[CriticalScalingVariable[delta,L,nu]] + a L^-omega;
LinearRGFlow[u0_,y_,ell_] := u0 Exp[y ell];
ClassifyRGDirection[y_] := Which[y>0,"relevant",y<0,"irrelevant",True,"marginal"];
GreenZeroFromHamiltonian[h_] := -Inverse[h];
TopologicalHamiltonianFromGreen[g_] := -Inverse[g];
Z2WilsonLoop[links_List] := Times@@links;
AreaLawWilson[area_,sigma_] := Exp[-sigma area];
NonFermiSelfEnergy[w_,a_:1,alpha_:2/3] := -I a Abs[w]^alpha;
OmegaTVariable[w_,t_,kb_:1] := w/(kb t);
OmegaTResponse[w_,t_,x_:.5,kb_:1] := t^-x/(1+OmegaTVariable[w,t,kb]^2);
PlanckianRate[t_,a_:1,kb_:1,hbar_:1] := a kb t/hbar;
NodalGap[theta_,delta0_:1,harmonic_:2] := delta0 Cos[harmonic theta];
DiracDOS[e_,vf_,vd_,deg_:4] := deg Abs[e]/(2 Pi vf vd);
MoireLength[a_,theta_] := a/(2 Abs[Sin[theta/2]]);
MoireProjectionHierarchy[w_,u_,gap_,tol_:.3] := {w/u,u/gap,w/u<tol && u/gap<tol};
FloquetPrethermalTime[omega_,j_,pref_:1] := pref Exp[omega/j];
