"""Chapter 41 computational companion: Hall experiments, materials, and metrology.

The routines are compact analytic diagnostics for transport extraction, metrology,
shot-noise charge inference, interferometric phase bookkeeping, and thermal-edge
acceptance. They are not substitutes for raw-data calibration or device-specific models.
"""
from __future__ import annotations
import math
import numpy as np

H_EXACT = 6.62607015e-34
E_EXACT = 1.602176634e-19
K_B_EXACT = 1.380649e-23
R_K = H_EXACT / E_EXACT**2
KAPPA0 = math.pi**2 * K_B_EXACT**2 / (3.0 * H_EXACT)


def hall_plateau_resistance(i: int) -> float:
    i = int(i)
    if i <= 0:
        raise ValueError("plateau index must be positive")
    return R_K / i


def conductivity_from_resistivity(rho_xx, rho_yx):
    """Return sigma_xx, sigma_xy for rho=[[rxx,-ryx],[ryx,rxx]]."""
    rxx = np.asarray(rho_xx, dtype=float)
    ryx = np.asarray(rho_yx, dtype=float)
    den = rxx**2 + ryx**2
    if np.any(den == 0):
        raise ValueError("singular resistivity tensor")
    return rxx / den, -ryx / den


def resistivity_from_conductivity(sigma_xx, sigma_xy):
    sxx = np.asarray(sigma_xx, dtype=float)
    sxy = np.asarray(sigma_xy, dtype=float)
    den = sxx**2 + sxy**2
    if np.any(den == 0):
        raise ValueError("singular conductivity tensor")
    return sxx / den, -sxy / den


def density_from_hall_slope(slope_ohm_per_tesla: float, charge: float = E_EXACT) -> float:
    slope = abs(float(slope_ohm_per_tesla)); q = abs(float(charge))
    if slope <= 0 or q <= 0:
        raise ValueError("positive slope magnitude and charge required")
    return 1.0 / (q * slope)


def mobility_from_sheet_resistance(density: float, sheet_resistance: float, charge: float = E_EXACT) -> float:
    n = float(density); r = float(sheet_resistance); q = abs(float(charge))
    if n <= 0 or r <= 0 or q <= 0:
        raise ValueError("positive density, resistance, and charge required")
    return 1.0 / (n * q * r)


def relative_hall_deviation(measured: float, i: int) -> float:
    target = hall_plateau_resistance(i)
    return (float(measured) - target) / target


def ccc_resistance_ratio(n1: int, n2: int, residual_fraction: float = 0.0) -> float:
    n1, n2 = int(n1), int(n2)
    if n1 <= 0 or n2 <= 0:
        raise ValueError("positive winding numbers required")
    return (n1 / n2) * (1.0 + float(residual_fraction))


def combined_standard_uncertainty(sensitivities, covariance) -> float:
    c = np.asarray(sensitivities, dtype=float)
    cov = np.asarray(covariance, dtype=float)
    if cov.shape != (len(c), len(c)):
        raise ValueError("covariance matrix shape mismatch")
    v = float(c @ cov @ c)
    if v < -1e-18:
        raise ValueError("negative propagated variance")
    return math.sqrt(max(v, 0.0))


def poisson_shot_noise(charge_coulomb: float, backscattered_current: float) -> float:
    return 2.0 * abs(float(charge_coulomb)) * abs(float(backscattered_current))


def effective_charge_from_poisson_noise(noise: float, backscattered_current: float) -> float:
    I = abs(float(backscattered_current))
    if I <= 0:
        raise ValueError("nonzero backscattered current required")
    return abs(float(noise)) / (2.0 * I)


def _coth(x: float) -> float:
    if abs(x) < 1e-6:
        return 1.0/x + x/3.0
    return 1.0 / math.tanh(x)


def finite_temperature_excess_noise(charge_coulomb: float, voltage: float, temperature: float, backscatter_conductance: float) -> float:
    """Weak-tunnelling interpolation with I_B=G_B V.

    S_ex = 2 q I_B coth(qV/2kT) - 4 kT G_B, with the V->0 limit set to 0.
    """
    q = abs(float(charge_coulomb)); V = float(voltage); T = float(temperature); G = abs(float(backscatter_conductance))
    if q <= 0 or T <= 0 or G < 0:
        raise ValueError("positive charge and temperature required")
    if abs(V) < 1e-18 or G == 0:
        return 0.0
    I = G * V
    x = q * V / (2.0 * K_B_EXACT * T)
    return max(0.0, 2.0*q*I*_coth(x) - 4.0*K_B_EXACT*T*G)


def laughlin_charge_fraction(m: int) -> float:
    m = int(m)
    if m <= 0 or m % 2 == 0:
        raise ValueError("positive odd Laughlin m required")
    return 1.0 / m


def laughlin_full_braid_phase(m: int) -> float:
    return 2.0 * math.pi * laughlin_charge_fraction(m)


def interferometer_phase(charge_fraction: float, flux_over_phi0: float, statistical_phase: float = 0.0, dynamical_phase: float = 0.0, coulomb_phase: float = 0.0) -> float:
    return (2.0*math.pi*float(charge_fraction)*float(flux_over_phi0)
            + float(statistical_phase) + float(dynamical_phase) + float(coulomb_phase))


def visibility_ratio(length: float, coherence_length: float) -> float:
    L, Lp = float(length), float(coherence_length)
    if L < 0 or Lp <= 0:
        raise ValueError("require L>=0 and positive coherence length")
    return math.exp(-L/Lp)


def equilibration_fraction(length: float, equilibration_length: float) -> float:
    L, Le = float(length), float(equilibration_length)
    if L < 0 or Le <= 0:
        raise ValueError("require L>=0 and positive equilibration length")
    return 1.0 - math.exp(-L/Le)


def thermal_hall_conductance(c_minus: float, temperature: float) -> float:
    T = float(temperature)
    if T < 0:
        raise ValueError("temperature must be nonnegative")
    return float(c_minus) * KAPPA0 * T


def ballistic_heat_current(c_minus: float, hot_temperature: float, cold_temperature: float) -> float:
    Th, Tc = float(hot_temperature), float(cold_temperature)
    if Th < 0 or Tc < 0:
        raise ValueError("temperatures must be nonnegative")
    return 0.5 * float(c_minus) * KAPPA0 * (Th**2 - Tc**2)


def five_halves_thermal_ratio(candidate: str) -> float:
    key = str(candidate).strip().lower().replace('_','-')
    data = {'pfaffian':3.5, 'anti-pfaffian':1.5, 'antipfaffian':1.5, 'ph-pfaffian':2.5, 'phpfaffian':2.5}
    if key not in data:
        raise ValueError("unknown benchmark candidate")
    return data[key]
