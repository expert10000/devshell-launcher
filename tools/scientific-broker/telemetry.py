"""Best-effort, explicitly attributed scientific broker resource measurements."""
import hashlib
import json
import platform
import shutil
import subprocess
import threading
import time

try:
    import psutil
except ImportError:
    psutil = None


def host_fingerprint():
    identity = {'node': platform.node(), 'system': platform.system(), 'release': platform.release(),
                'machine': platform.machine(), 'processor': platform.processor(),
                'logicalCpus': psutil.cpu_count() if psutil else None,
                'ramBytes': psutil.virtual_memory().total if psutil else None}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def measurement(state, collector, unit, scope, value=None, samples=0, reason=None):
    return {'state': state, 'collector': collector, 'unit': unit, 'scope': scope,
            'value': value, 'samples': samples, 'reason': reason}


class ResourceSampler:
    def __init__(self, pid):
        self.pid = pid
        self.stop_event = threading.Event()
        self.thread = None
        self.processes = {}
        self.cpu_seconds = {}
        self.peak_rss = None
        self.cpu_samples = 0
        self.ram_samples = 0
        self.gpu = []
        self.gpu_reason = None
        self.nvidia_smi = shutil.which('nvidia-smi')

    def start(self):
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()

    def _sample_processes(self):
        if psutil is None:
            return
        try:
            root = psutil.Process(self.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return
        processes = [root]
        try:
            processes.extend(root.children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        rss = 0
        measured_rss = False
        measured_cpu = False
        for process in processes:
            try:
                identity = (process.pid, process.create_time())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            self.processes[identity] = 'unavailable'
            try:
                self.processes[identity] = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            try:
                cpu = process.cpu_times()
                self.cpu_seconds[identity] = max(self.cpu_seconds.get(identity, 0), cpu.user + cpu.system)
                measured_cpu = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            try:
                rss += process.memory_info().rss
                measured_rss = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if measured_rss:
            self.peak_rss = max(self.peak_rss or 0, rss)
            self.ram_samples += 1
        if measured_cpu:
            self.cpu_samples += 1

    def _sample_gpu(self):
        if not self.nvidia_smi:
            self.gpu_reason = 'nvidia-smi is unavailable'
            return
        try:
            command = [self.nvidia_smi, '--query-gpu=utilization.gpu,memory.used', '--format=csv,noheader,nounits']
            result = subprocess.run(command, capture_output=True, text=True, timeout=3)
            if result.returncode:
                raise ValueError(result.stderr.strip() or 'nvidia-smi failed')
            rows = [tuple(float(value.strip()) for value in line.split(','))
                    for line in result.stdout.splitlines() if line.strip()]
            if not rows or any(len(row) != 2 for row in rows):
                raise ValueError('nvidia-smi returned no GPU measurements')
            self.gpu.append((max(row[0] for row in rows), sum(row[1] for row in rows)))
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            self.gpu_reason = str(error)[:200]

    def _sample(self):
        next_gpu = 0.0
        while not self.stop_event.is_set():
            self._sample_processes()
            if time.monotonic() >= next_gpu:
                self._sample_gpu()
                next_gpu = time.monotonic() + 0.5
            self.stop_event.wait(0.025)
        self._sample_processes()

    def finish(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=4)
        cpu = measurement('recorded', 'psutil process-tree cpu_times', 's', 'broker worker tree',
                          round(sum(self.cpu_seconds.values()), 6), self.cpu_samples) if self.cpu_samples else \
              measurement('unavailable', 'psutil process-tree cpu_times', 's', 'broker worker tree',
                          reason='psutil unavailable or worker exited before sampling')
        ram = measurement('recorded', 'psutil process-tree memory_info.rss', 'byte', 'broker worker tree',
                          self.peak_rss, self.ram_samples) if self.ram_samples else \
              measurement('unavailable', 'psutil process-tree memory_info.rss', 'byte', 'broker worker tree',
                          reason='psutil unavailable or worker exited before sampling')
        gpu = measurement('recorded', 'nvidia-smi utilization.gpu', '%', 'host GPUs, not job-attributed',
                          max(row[0] for row in self.gpu), len(self.gpu)) if self.gpu else \
              measurement('unavailable', 'nvidia-smi utilization.gpu', '%', 'host GPUs, not job-attributed',
                          reason=self.gpu_reason or 'no GPU sample completed')
        vram = measurement('recorded', 'nvidia-smi memory.used', 'MiB', 'host GPUs, not job-attributed',
                           max(row[1] for row in self.gpu), len(self.gpu)) if self.gpu else \
               measurement('unavailable', 'nvidia-smi memory.used', 'MiB', 'host GPUs, not job-attributed',
                           reason=self.gpu_reason or 'no VRAM sample completed')
        return {'schemaVersion': 1, 'hostFingerprintSha256': host_fingerprint(),
                'cpu': cpu, 'ram': ram, 'gpu': gpu, 'vram': vram,
                'observedProcesses': [{'pid': pid, 'createTime': created, 'name': name}
                                      for (pid, created), name in sorted(self.processes.items())]}


def active_processes(observed):
    if psutil is None:
        return None
    active = []
    for item in observed:
        try:
            process = psutil.Process(item['pid'])
            if (abs(process.create_time() - item['createTime']) < 0.001 and process.is_running()
                    and process.status() != psutil.STATUS_ZOMBIE):
                active.append(item['pid'])
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            return None
    return active


def stop_observed(observed):
    if psutil is None:
        return None
    inaccessible = False
    for item in observed:
        try:
            process = psutil.Process(item['pid'])
            if abs(process.create_time() - item['createTime']) < 0.001 and process.is_running():
                process.kill()
                process.wait(timeout=2)
        except psutil.AccessDenied:
            inaccessible = True
        except (psutil.NoSuchProcess, psutil.TimeoutExpired):
            continue
    return None if inaccessible else active_processes(observed)
