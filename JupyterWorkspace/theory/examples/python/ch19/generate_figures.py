from __future__ import annotations
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from classical_crisis_companion import (
    E_CHARGE, H, DiagnosticDashboard, compton_shift,
    diagnostic_activation_fraction, empirical_stopping_potential,
    fit_origin_slope, gaussian_line_spectrum, quadratic_relative_spacing,
    rayleigh_jeans_integrated, weighted_chi_square,
)

OUT = Path('generated/ch19/computational')
OUT.mkdir(parents=True, exist_ok=True)


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUT / name, bbox_inches='tight')
    plt.close()

cutoffs = np.logspace(12, 15, 160)
plt.figure(figsize=(6.2, 3.8))
plt.loglog(cutoffs, rayleigh_jeans_integrated(cutoffs, 300.0))
plt.xlabel('cutoff frequency (Hz)'); plt.ylabel('integrated energy density (J m$^{-3}$)')
plt.title('Classical ultraviolet cutoff dependence'); plt.grid(True, which='both', alpha=.25)
save('ultraviolet_cutoff.pdf')

t = np.logspace(0, 4, 180)
plt.figure(figsize=(6.2, 3.8))
for delta_ev in [0.005, 0.02, 0.08]:
    plt.semilogx(t, diagnostic_activation_fraction(delta_ev * E_CHARGE, t), label=f'{delta_ev:g} eV')
plt.xlabel('temperature (K)'); plt.ylabel('diagnostic activation fraction'); plt.ylim(-.02,1.02)
plt.title('Mode-access scale diagnostic'); plt.legend(); plt.grid(True, alpha=.25)
save('mode_activation.pdf')

phi = 2.1 * E_CHARGE
nu = np.linspace(2e14, 1.1e15, 220)
plt.figure(figsize=(6.2, 3.8))
plt.plot(nu/1e14, empirical_stopping_potential(nu, phi), label='empirical threshold law')
plt.plot(nu/1e14, 0.35*np.ones_like(nu), '--', label='threshold-free intensity surrogate')
plt.xlabel('frequency ($10^{14}$ Hz)'); plt.ylabel('stopping potential (V)')
plt.title('Competing photoelectric model forms'); plt.legend(); plt.grid(True, alpha=.25)
save('photoelectric_models.pdf')

th = np.linspace(0, np.pi, 240)
plt.figure(figsize=(6.2, 3.8))
plt.plot(np.degrees(th), compton_shift(th)*1e12)
plt.xlabel('scattering angle (degrees)'); plt.ylabel('wavelength shift (pm)')
plt.title('Compton angular fingerprint'); plt.grid(True, alpha=.25)
save('compton_angle.pdf')

x = np.linspace(-2, 2, 21); y = x**2 + 0.03*np.sin(9*x)
a = fit_origin_slope(x, y)
res = y-a*x
fig, ax = plt.subplots(figsize=(6.2,3.8))
ax.plot(x,y,'o',label='synthetic observations'); ax.plot(x,a*x,label='best origin-constrained line')
ax.set_xlabel('x'); ax.set_ylabel('y'); ax.set_title('Wrong model form leaves structured residuals')
ax.legend(); ax.grid(True,alpha=.25)
save('residual_fingerprint.pdf')

sigma=np.full_like(x,.08)
quad=x**2
line=a*x
chis=[weighted_chi_square(y,line,sigma),weighted_chi_square(y,quad,sigma)]
plt.figure(figsize=(5.4,3.8)); plt.bar(['linear form','quadratic form'],chis)
plt.ylabel('$\\chi^2$'); plt.title('Weighted model comparison'); plt.grid(True,axis='y',alpha=.25)
save('chi_square_comparison.pdf')

axis=np.linspace(0,10,4000); centers=np.arange(1,10); amps=np.exp(-0.08*(centers-5)**2)
fine=gaussian_line_spectrum(axis,centers,amps,.035); coarse=gaussian_line_spectrum(axis,centers,amps,.55)
plt.figure(figsize=(6.2,3.8)); plt.plot(axis,fine,label='high resolution'); plt.plot(axis,coarse,label='coarse resolution')
plt.xlabel('spectral coordinate'); plt.ylabel('normalized signal'); plt.title('Discrete lines under finite resolution')
plt.legend(); plt.grid(True,alpha=.25)
save('spectral_blurring.pdf')

n=np.arange(1,201)
plt.figure(figsize=(6.2,3.8)); plt.loglog(n,quadratic_relative_spacing(n))
plt.xlabel('level index n'); plt.ylabel('relative adjacent spacing'); plt.title('One route to correspondence')
plt.grid(True,which='both',alpha=.25)
save('correspondence_spacing.pdf')

vals=DiagnosticDashboard(.35,250.0,80.0,1.4).as_array()
plt.figure(figsize=(6.2,3.8)); plt.bar(['$k_BT/\\Delta E$','$\\delta E_{inst}/\\Delta E$','$S/h$','reduced residual'],np.log10(1+vals))
plt.ylabel('$\\log_{10}(1+x)$'); plt.title('Dimensionless anomaly dashboard'); plt.grid(True,axis='y',alpha=.25)
save('anomaly_dashboard.pdf')

summary={
    'tests_required':12,
    'ultraviolet_cutoff_ratio_2x':float(rayleigh_jeans_integrated(2e14,300)/rayleigh_jeans_integrated(1e14,300)),
    'photoelectric_threshold_hz':float(phi/H),
    'compton_backscatter_pm':float(compton_shift(np.pi)*1e12),
    'linear_chi_square':float(chis[0]),
    'quadratic_chi_square':float(chis[1]),
    'dashboard':vals.tolist(),
    'synthetic_data_notice':'Residual and dashboard plots use synthetic diagnostic data.'
}
(OUT/'diagnostics.json').write_text(json.dumps(summary,indent=2)+'\n')
