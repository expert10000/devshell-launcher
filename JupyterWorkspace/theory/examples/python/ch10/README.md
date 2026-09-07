# Chapter 10 Python companion

The companion is organized as a reusable library, a deterministic artifact
generator, and a regression suite.

```bash
python3 -m pip install -r examples/python/ch10/requirements.txt
python3 examples/python/ch10/generate_companion.py
PYTHONPATH=examples/python/ch10 python3 -m unittest examples/python/ch10/test_companion.py
```

`lagrangian_dynamics.py` contains symbolic Euler--Lagrange construction,
Runge--Kutta integration, pendulum and constraint diagnostics, effective
potentials, generalized normal modes, and uniform-field charged-particle
motion. `generate_companion.py` writes seven vector-PDF figures, a deterministic
JSON summary, and CSV diagnostics under `generated/ch10/computational/`.
