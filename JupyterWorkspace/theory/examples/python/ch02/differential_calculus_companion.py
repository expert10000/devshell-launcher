"""Computational companion for Chapter 2: Differential Calculus."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parents[3] / "generated" / "ch02"
OUT.mkdir(parents=True, exist_ok=True)


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)


def surface_and_contours() -> None:
    x = np.linspace(-2.5, 2.5, 180)
    y = np.linspace(-2.5, 2.5, 180)
    X, Y = np.meshgrid(x, y)
    Z = X**2 + 0.5 * Y**2
    fig = plt.figure(figsize=(6.2, 4.7))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, Z, rstride=5, cstride=5, linewidth=0.15, alpha=0.85)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("f(x,y)")
    ax.set_title(r"Surface: $f(x,y)=x^2+\frac{1}{2} y^2$")
    save(fig, "surface_plot.pdf")


def gradient_field() -> None:
    x = np.linspace(-2.2, 2.2, 19)
    y = np.linspace(-2.2, 2.2, 19)
    X, Y = np.meshgrid(x, y)
    F = X**2 + Y**2
    U, V = 2 * X, 2 * Y
    mag = np.hypot(U, V)
    U = np.divide(U, mag, out=np.zeros_like(U), where=mag > 0)
    V = np.divide(V, mag, out=np.zeros_like(V), where=mag > 0)
    fig, ax = plt.subplots(figsize=(5.8, 5.0))
    ax.contour(X, Y, F, levels=9)
    ax.quiver(X, Y, U, V)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title(r"Normalized gradient field of $f=x^2+y^2$")
    save(fig, "gradient_field.pdf")


def jacobian_transformation() -> None:
    u = np.linspace(-1.5, 1.5, 17)
    v = np.linspace(-1.5, 1.5, 17)
    fig, ax = plt.subplots(figsize=(6.0, 5.0))
    for c in u:
        vv = np.linspace(-1.5, 1.5, 200)
        xx = c + 0.35 * vv
        yy = 0.25 * c + vv + 0.12 * c * vv
        ax.plot(xx, yy, linewidth=0.8)
    for c in v:
        uu = np.linspace(-1.5, 1.5, 200)
        xx = uu + 0.35 * c
        yy = 0.25 * uu + c + 0.12 * uu * c
        ax.plot(xx, yy, linewidth=0.8)
    ax.set_aspect("equal")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("A nonlinear coordinate map and its local Jacobian")
    save(fig, "jacobian_grid.pdf")


def directional_derivative() -> None:
    theta = np.linspace(0, 2 * np.pi, 400)
    grad = np.array([3.0, 1.0])
    rates = grad[0] * np.cos(theta) + grad[1] * np.sin(theta)
    fig, ax = plt.subplots(figsize=(6.0, 4.2))
    ax.plot(theta, rates)
    ax.axhline(np.linalg.norm(grad), linestyle="--", linewidth=0.8)
    ax.axhline(-np.linalg.norm(grad), linestyle="--", linewidth=0.8)
    ax.set_xlabel(r"direction angle $\theta$")
    ax.set_ylabel(r"$D_{\hat{u}}f$")
    ax.set_title(r"Directional derivative for $\nabla f=(3,1)$")
    ax.set_xticks([0, np.pi / 2, np.pi, 3 * np.pi / 2, 2 * np.pi])
    ax.set_xticklabels(["0", r"$\pi/2$", r"$\pi$", r"$3\pi/2$", r"$2\pi$"])
    save(fig, "directional_derivative.pdf")


def numerical_jacobian(func, point: np.ndarray, step: float = 1e-6) -> np.ndarray:
    point = np.asarray(point, dtype=float)
    f0 = np.asarray(func(point), dtype=float)
    jac = np.empty((f0.size, point.size), dtype=float)
    for j in range(point.size):
        delta = np.zeros_like(point)
        delta[j] = step
        jac[:, j] = (np.asarray(func(point + delta)) - np.asarray(func(point - delta))) / (2 * step)
    return jac


def verify_numerical_jacobian() -> None:
    func = lambda q: np.array([q[0] ** 2 * q[1], np.sin(q[0] + q[1])])
    p = np.array([1.2, -0.4])
    numeric = numerical_jacobian(func, p)
    exact = np.array([[2 * p[0] * p[1], p[0] ** 2], [np.cos(p.sum()), np.cos(p.sum())]])
    if not np.allclose(numeric, exact, rtol=1e-5, atol=1e-7):
        raise RuntimeError("Numerical Jacobian verification failed")
    print("Numerical Jacobian verified at", p)
    print(numeric)


if __name__ == "__main__":
    surface_and_contours()
    gradient_field()
    jacobian_transformation()
    directional_derivative()
    verify_numerical_jacobian()
