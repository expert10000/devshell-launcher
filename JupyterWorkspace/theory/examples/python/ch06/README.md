# Chapter 6 Python Companion

The companion reproduces the chapter's central numerical constructions:

- numerical rank and null space by SVD;
- modified Gram--Schmidt and reduced QR factorization;
- Hermitian eigensystems and spectral projectors;
- unitary time evolution from a matrix exponential;
- Bloch-vector extraction for a two-level state;
- truncated Fourier reconstruction.

## Requirements

- Python 3.10 or later
- NumPy 1.24 or later

## Run

From the repository root:

```bash
python3 examples/python/ch06/linear_algebra_hilbert_companion.py
```

The script is deterministic and writes numerical diagnostics to standard output. It does not write generated assets into the source tree.
