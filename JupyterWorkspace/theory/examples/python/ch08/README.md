# Chapter 8 Python Companion

This deterministic companion implements and visualizes the central numerical ideas of Chapter 8:

- constant-acceleration trajectories;
- projectile families;
- polar-coordinate velocity and acceleration;
- relative motion and closest approach;
- centered finite differences;
- noise amplification under differentiation;
- least-squares reconstruction of motion;
- Monte Carlo propagation of launch uncertainty.

## Requirements

- Python 3.10 or later
- NumPy 1.24 or later
- Matplotlib 3.7 or later

Install the requirements from the repository root:

```bash
python3 -m pip install -r examples/python/ch08/requirements.txt
```

## Generate the companion outputs

```bash
python3 examples/python/ch08/generate_companion.py
```

The command writes seven vector-PDF figures plus JSON and CSV diagnostics to:

```text
generated/ch08/computational/
```

Use another output directory without modifying the source tree:

```bash
python3 examples/python/ch08/generate_companion.py --output-dir /tmp/ch08-motion
```

## Run the regression tests

```bash
PYTHONPATH=examples/python/ch08 python3 -m unittest examples/python/ch08/test_companion.py
```

All random calculations use fixed seeds so that the release figures and diagnostics are reproducible.
