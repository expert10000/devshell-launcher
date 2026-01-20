using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace BatchLauncher;

internal sealed class ConPtyProcess : IDisposable
{
    private const int ProcThreadAttributePseudoConsole = 0x00020016;
    private const int ExtendedStartupinfoPresent = 0x00080000;
    private const int WaitObject0 = 0x00000000;
    private const int WaitTimeout = 0x00000102;
    private const int CreateUnicodeEnvironment = 0x00000400;

    public IntPtr PseudoConsole { get; private set; }
    public SafeFileHandle InputWrite { get; }
    public SafeFileHandle OutputRead { get; }
    public SafeFileHandle ProcessHandle { get; }
    public SafeFileHandle ThreadHandle { get; }

    private ConPtyProcess(
        IntPtr pseudoConsole,
        SafeFileHandle inputWrite,
        SafeFileHandle outputRead,
        SafeFileHandle processHandle,
        SafeFileHandle threadHandle)
    {
        PseudoConsole = pseudoConsole;
        InputWrite = inputWrite;
        OutputRead = outputRead;
        ProcessHandle = processHandle;
        ThreadHandle = threadHandle;
    }

    public static ConPtyProcess Start(string application, string? arguments, int cols, int rows)
    {
        if (!CreatePipe(out var ptyInputRead, out var inputWrite, IntPtr.Zero, 0))
        {
            throw new InvalidOperationException($"CreatePipe failed: {Marshal.GetLastWin32Error()}");
        }

        if (!CreatePipe(out var outputRead, out var ptyOutputWrite, IntPtr.Zero, 0))
        {
            ptyInputRead.Dispose();
            inputWrite.Dispose();
            throw new InvalidOperationException($"CreatePipe failed: {Marshal.GetLastWin32Error()}");
        }

        var size = new COORD((short)cols, (short)rows);
        var hr = CreatePseudoConsole(size, ptyInputRead, ptyOutputWrite, 0, out var pseudoConsole);
        ptyInputRead.Dispose();
        ptyOutputWrite.Dispose();

        if (hr != 0)
        {
            inputWrite.Dispose();
            outputRead.Dispose();
            throw new InvalidOperationException($"CreatePseudoConsole failed: 0x{hr:X8}");
        }

        var startupInfo = new STARTUPINFOEX();
        startupInfo.StartupInfo.cb = Marshal.SizeOf<STARTUPINFOEX>();

        var attributeSize = IntPtr.Zero;
        InitializeProcThreadAttributeList(IntPtr.Zero, 1, 0, ref attributeSize);

        startupInfo.lpAttributeList = Marshal.AllocHGlobal(attributeSize);
        if (!InitializeProcThreadAttributeList(startupInfo.lpAttributeList, 1, 0, ref attributeSize))
        {
            CleanupFailedStart(pseudoConsole, inputWrite, outputRead);
            throw new InvalidOperationException($"InitializeProcThreadAttributeList failed: {Marshal.GetLastWin32Error()}");
        }

        if (!UpdateProcThreadAttribute(
                startupInfo.lpAttributeList,
                0,
                (IntPtr)ProcThreadAttributePseudoConsole,
                pseudoConsole,
                (IntPtr)IntPtr.Size,
                IntPtr.Zero,
                IntPtr.Zero))
        {
            DeleteProcThreadAttributeList(startupInfo.lpAttributeList);
            Marshal.FreeHGlobal(startupInfo.lpAttributeList);
            CleanupFailedStart(pseudoConsole, inputWrite, outputRead);
            throw new InvalidOperationException($"UpdateProcThreadAttribute failed: {Marshal.GetLastWin32Error()}");
        }

        var commandLine = string.IsNullOrWhiteSpace(arguments)
            ? $"\"{application}\""
            : $"\"{application}\" {arguments}";
        var commandLineBuilder = new StringBuilder(commandLine);
        var created = CreateProcess(
            application,
            commandLineBuilder,
            IntPtr.Zero,
            IntPtr.Zero,
            false,
            ExtendedStartupinfoPresent | CreateUnicodeEnvironment,
            IntPtr.Zero,
            null,
            ref startupInfo,
            out var processInfo);

        DeleteProcThreadAttributeList(startupInfo.lpAttributeList);
        Marshal.FreeHGlobal(startupInfo.lpAttributeList);

        if (!created)
        {
            CleanupFailedStart(pseudoConsole, inputWrite, outputRead);
            throw new InvalidOperationException($"CreateProcess failed: {Marshal.GetLastWin32Error()}");
        }

        return new ConPtyProcess(
            pseudoConsole,
            inputWrite,
            outputRead,
            new SafeFileHandle(processInfo.hProcess, ownsHandle: true),
            new SafeFileHandle(processInfo.hThread, ownsHandle: true));
    }

    public void Resize(int cols, int rows)
    {
        var size = new COORD((short)cols, (short)rows);
        ResizePseudoConsole(PseudoConsole, size);
    }

    public int WaitForExit(CancellationToken token)
    {
        if (ProcessHandle.IsInvalid)
        {
            return -1;
        }

        var handle = ProcessHandle.DangerousGetHandle();
        while (!token.IsCancellationRequested)
        {
            var result = WaitForSingleObject(handle, 100);
            if (result == WaitObject0)
            {
                break;
            }

            if (result != WaitTimeout)
            {
                break;
            }
        }

        if (GetExitCodeProcess(handle, out var exitCode))
        {
            return unchecked((int)exitCode);
        }

        return -1;
    }

    public void Dispose()
    {
        if (PseudoConsole != IntPtr.Zero)
        {
            ClosePseudoConsole(PseudoConsole);
            PseudoConsole = IntPtr.Zero;
        }

        InputWrite.Dispose();
        OutputRead.Dispose();
        ProcessHandle.Dispose();
        ThreadHandle.Dispose();
    }

    private static void CleanupFailedStart(IntPtr pseudoConsole, SafeFileHandle inputWrite, SafeFileHandle outputRead)
    {
        if (pseudoConsole != IntPtr.Zero)
        {
            ClosePseudoConsole(pseudoConsole);
        }

        inputWrite.Dispose();
        outputRead.Dispose();
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct COORD
    {
        public short X;
        public short Y;

        public COORD(short x, short y)
        {
            X = x;
            Y = y;
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct STARTUPINFO
    {
        public int cb;
        public string? lpReserved;
        public string? lpDesktop;
        public string? lpTitle;
        public int dwX;
        public int dwY;
        public int dwXSize;
        public int dwYSize;
        public int dwXCountChars;
        public int dwYCountChars;
        public int dwFillAttribute;
        public int dwFlags;
        public short wShowWindow;
        public short cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct STARTUPINFOEX
    {
        public STARTUPINFO StartupInfo;
        public IntPtr lpAttributeList;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PROCESS_INFORMATION
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public int dwProcessId;
        public int dwThreadId;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CreatePipe(
        out SafeFileHandle hReadPipe,
        out SafeFileHandle hWritePipe,
        IntPtr lpPipeAttributes,
        int nSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern int CreatePseudoConsole(
        COORD size,
        SafeFileHandle hInput,
        SafeFileHandle hOutput,
        int dwFlags,
        out IntPtr phPC);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern int ResizePseudoConsole(IntPtr hPC, COORD size);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern void ClosePseudoConsole(IntPtr hPC);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool InitializeProcThreadAttributeList(
        IntPtr lpAttributeList,
        int dwAttributeCount,
        int dwFlags,
        ref IntPtr lpSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool UpdateProcThreadAttribute(
        IntPtr lpAttributeList,
        int dwFlags,
        IntPtr attribute,
        IntPtr lpValue,
        IntPtr cbSize,
        IntPtr lpPreviousValue,
        IntPtr lpReturnSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern void DeleteProcThreadAttributeList(IntPtr lpAttributeList);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CreateProcess(
        string? lpApplicationName,
        StringBuilder lpCommandLine,
        IntPtr lpProcessAttributes,
        IntPtr lpThreadAttributes,
        bool bInheritHandles,
        int dwCreationFlags,
        IntPtr lpEnvironment,
        string? lpCurrentDirectory,
        ref STARTUPINFOEX lpStartupInfo,
        out PROCESS_INFORMATION lpProcessInformation);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern int WaitForSingleObject(IntPtr hHandle, int dwMilliseconds);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetExitCodeProcess(IntPtr hProcess, out uint lpExitCode);
}
