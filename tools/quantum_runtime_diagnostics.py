"""Read-only Theory Lab worker probe for DevShell's science runtime review."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from time import perf_counter


def probe(repository: Path, benchmark: bool = False):
    worker_root = repository / "workers" / "quantum-python"
    if not (worker_root / "quantum_worker" / "main.py").is_file():
        raise ValueError("Theory Lab quantum worker source is missing")
    sys.path.insert(0, str(worker_root))
    from quantum_worker import __version__
    from quantum_worker.main import handle
    from quantum_worker.engines.native_engine import diagonalize

    responses = {}
    for method in ("hello", "health", "capabilities", "resources"):
        response, stop = handle(json.dumps({"jsonrpc": "2.0", "id": method, "method": method, "params": {}}))
        if stop or not response or "error" in response:
            raise RuntimeError(f"Worker {method} probe failed: {response.get('error') if response else 'no response'}")
        responses[method] = response["result"]
    if responses["hello"]["workerVersion"] != __version__ or responses["health"]["status"] != "ok":
        raise RuntimeError("Worker version or health response disagrees")

    job = json.loads((repository / "packages" / "contracts" / "fixtures" / "two-level.job.json").read_text(encoding="utf-8"))
    job["engine"] = "native"
    started = perf_counter()
    first = diagonalize(job)
    native_ms = (perf_counter() - started) * 1000
    second = diagonalize(job)
    energies = first["spectrum"]["eigenvalues"]
    expected = math.hypot(1, 0.8) / 2
    passed = len(energies) == 2 and abs(energies[0] + expected) < 1e-12 and abs(energies[1] - expected) < 1e-12
    passed = passed and energies == second["spectrum"]["eigenvalues"]
    digest = hashlib.sha256(json.dumps(energies, separators=(",", ":")).encode()).hexdigest()
    report = {
        "schema": "devshell.quantum-runtime-diagnostics/v1",
        "host": {"system": platform.system(), "machine": platform.machine()},
        "pythonVersion": platform.python_version(),
        "workerVersion": __version__,
        "workerHealth": responses["health"]["status"],
        "capabilities": responses["capabilities"],
        "resources": responses["resources"],
        "fixture": {"name": "two-level.job.json", "engine": "native", "passed": passed,
                    "energies": energies, "energySha256": digest, "nativeMs": round(native_ms, 3)},
    }
    if benchmark:
        from quantum_worker.acceleration import benchmark_evolution
        report["backendBenchmark"] = benchmark_evolution()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path, help="Theory Lab checkout")
    parser.add_argument("--report", type=Path, help="Write a reproducibility report as JSON")
    parser.add_argument("--benchmark", action="store_true", help="Compare optional accelerated backend with native reference")
    args = parser.parse_args()
    try:
        report = probe(args.repository.resolve(), args.benchmark)
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(output, encoding="utf-8")
        print(output, end="")
        return 0 if report["fixture"]["passed"] else 1
    except Exception as error:
        print(json.dumps({"schema": "devshell.quantum-runtime-diagnostics/v1", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
