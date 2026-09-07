# Chapter 9 Python Companion

This deterministic companion turns the principal models of Newtonian mechanics
into reusable numerical experiments:

- force superposition and the mass-dependent response to net force;
- static-to-kinetic friction regime changes;
- Atwood-machine parameter sweeps;
- vertical-circle contact conditions;
- linear and quadratic drag;
- inertial and rotating coordinate descriptions;
- inverse-dynamics reconstruction from noisy trajectory data.

## Requirements

- Python 3.10 or later
- NumPy 1.24 or later
- Matplotlib 3.7 or later

Install from the repository root:

```bash
python3 -m pip install -r examples/python/ch09/requirements.txt
```

## Generate the release artifacts

```bash
python3 examples/python/ch09/generate_companion.py
```

The command writes seven vector-PDF figures plus JSON and CSV diagnostics to:

```text
generated/ch09/computational/
```

Use an alternate output directory without changing the repository:

```bash
python3 examples/python/ch09/generate_companion.py --output-dir /tmp/ch09-dynamics
```

## Run the regression tests

```bash
PYTHONPATH=examples/python/ch09 python3 -m unittest examples/python/ch09/test_companion.py
```

All stochastic calculations use fixed seeds, so committed diagnostics are
reproducible.
