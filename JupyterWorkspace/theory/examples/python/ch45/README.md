# Chapter 45 computational companion

Run from the repository root:

```bash
python -m pytest -q examples/python/ch45/test_topological_insulators_companion.py
python examples/python/ch45/generate_figures.py
```

The suite fixes a spinful time-reversal-symmetric four-band lattice model, checks Z2 diagnostics through parity and spin-block Chern parity, tests occupied-subspace Wilson-loop gauge invariance, and verifies the finite-size, helical-edge, surface-Dirac, magnetoelectric, and surface/bulk acceptance relations used in Chapter 45.
