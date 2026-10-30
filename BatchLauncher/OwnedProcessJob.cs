using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace BatchLauncher;

internal sealed class OwnedProcessJob : IDisposable
{
    private readonly SafeFileHandle _handle = CreateJobObject(IntPtr.Zero, null);
    private readonly object _trackSync = new();
    private readonly Dictionary<int, Process> _tracked = new();
    private readonly CancellationTokenSource _trackingCancellation = new();
    private Task? _trackingTask;
    public OwnedProcessJob()
    {
        if (_handle.IsInvalid) throw new Win32Exception();
        var limits = new ExtendedLimits { Basic = new BasicLimits { Flags = 0x2000 } };
        if (!SetInformationJobObject(_handle, 9, ref limits, (uint)Marshal.SizeOf<ExtendedLimits>())) throw new Win32Exception();
    }
    public void Add(Process process)
    {
        if (!AssignProcessToJobObject(_handle, process.Handle)) throw new Win32Exception();
        var trackedRoot = Process.GetProcessById(process.Id);
        _ = trackedRoot.Handle;
        lock (_trackSync) _tracked[process.Id] = trackedRoot;
        _trackingTask = Task.Run(async () =>
        {
            while (!_trackingCancellation.IsCancellationRequested)
            {
                try { RefreshDescendants(); }
                catch (Win32Exception) { }
                try { await Task.Delay(100, _trackingCancellation.Token); }
                catch (OperationCanceledException) { break; }
            }
        });
    }
    public bool HasProcesses
    {
        get
        {
            var data = new byte[48];
            if (!QueryInformationJobObject(_handle, 1, data, 48, IntPtr.Zero)) throw new Win32Exception();
            return BitConverter.ToUInt32(data, 40) != 0;
        }
    }
    public void Stop()
    {
        if (_handle.IsClosed) return;
        _trackingCancellation.Cancel();
        try
        {
            // npm and other package runners can detach descendants from the job.
            // Preserve process handles as they appear, then stop only that tree.
            RefreshDescendants();
            List<Process> processes;
            lock (_trackSync) processes = _tracked.Values.ToList();
            foreach (var process in processes)
            {
                try { if (!process.HasExited) process.Kill(entireProcessTree: true); }
                catch (InvalidOperationException) { }
                catch (Win32Exception) { }
            }
        }
        finally { TerminateJobObject(_handle, 1); }
    }
    private void RefreshDescendants()
    {
        var snapshot = CreateToolhelp32Snapshot(0x2, 0);
        if (snapshot == new IntPtr(-1)) throw new Win32Exception();
        try
        {
            var children = new Dictionary<int, List<int>>();
            var entry = new ProcessEntry { Size = (uint)Marshal.SizeOf<ProcessEntry>() };
            if (Process32First(snapshot, ref entry))
                do
                {
                    if (!children.TryGetValue((int)entry.ParentId, out var list)) children[(int)entry.ParentId] = list = new();
                    list.Add((int)entry.ProcessId);
                    entry.Size = (uint)Marshal.SizeOf<ProcessEntry>();
                } while (Process32Next(snapshot, ref entry));
            lock (_trackSync)
            {
                var queue = new Queue<int>(_tracked.Keys);
                while (queue.TryDequeue(out var parent))
                    if (children.TryGetValue(parent, out var descendants))
                        foreach (var id in descendants)
                        {
                            if (_tracked.ContainsKey(id)) continue;
                            try { var process = Process.GetProcessById(id); _ = process.Handle; _tracked[id] = process; queue.Enqueue(id); }
                            catch (ArgumentException) { }
                            catch (Win32Exception) { }
                        }
            }
        }
        finally { CloseHandle(snapshot); }
    }
    public void Dispose()
    {
        _trackingCancellation.Cancel();
        _trackingTask?.Wait(TimeSpan.FromSeconds(1));
        lock (_trackSync) foreach (var process in _tracked.Values) process.Dispose();
        _trackingCancellation.Dispose();
        _handle.Dispose();
    }
    [StructLayout(LayoutKind.Sequential)] private struct BasicLimits
    {
        public long ProcessTime, JobTime; public uint Flags; public UIntPtr Min, Max; public uint Active; public UIntPtr Affinity; public uint Priority, Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] private struct ExtendedLimits
    {
        public BasicLimits Basic; public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)] private struct ProcessEntry
    {
        public uint Size, Usage, ProcessId;
        public UIntPtr DefaultHeapId;
        public uint ModuleId, Threads, ParentId;
        public int Priority;
        public uint Flags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string ExeFile;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern SafeFileHandle CreateJobObject(IntPtr attributes, string? name);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool SetInformationJobObject(SafeFileHandle job, int kind, ref ExtendedLimits info, uint size);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool AssignProcessToJobObject(SafeFileHandle job, IntPtr process);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool QueryInformationJobObject(SafeFileHandle job, int kind, byte[] info, uint size, IntPtr length);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool TerminateJobObject(SafeFileHandle job, uint exitCode);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern bool Process32First(IntPtr snapshot, ref ProcessEntry entry);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern bool Process32Next(IntPtr snapshot, ref ProcessEntry entry);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool CloseHandle(IntPtr handle);
}
