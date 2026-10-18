namespace BatchLauncher;

public partial class Form1
{
    private FormWindowState _lastVisibleWindowState = FormWindowState.Normal;
    private static string WindowPlacementPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DevShellLauncher", "window-placement.json");

    private void InitializeWindowPlacement()
    {
        Load += (_, _) =>
        {
            var placement = WindowPlacementStore.Fit(WindowPlacementStore.Load(WindowPlacementPath),
                Screen.AllScreens.Select(screen => screen.WorkingArea).ToArray(), MinimumSize);
            if (placement == null) return;
            StartPosition = FormStartPosition.Manual;
            Bounds = new Rectangle(placement.X, placement.Y, placement.Width, placement.Height);
            WindowState = placement.Maximized ? FormWindowState.Maximized : FormWindowState.Normal;
            _lastVisibleWindowState = WindowState;
        };
    }

    protected override void WndProc(ref Message message)
    {
        base.WndProc(ref message);
        // WM_SIZE reports the native show state, including restores performed outside WinForms.
        if (message.Msg == 0x0005 && message.WParam.ToInt64() is 0 or 2)
            _lastVisibleWindowState = message.WParam.ToInt64() == 2 ? FormWindowState.Maximized : FormWindowState.Normal;
    }

    private void SaveWindowPlacement()
    {
        var bounds = WindowState == FormWindowState.Normal ? Bounds : RestoreBounds;
        if (bounds.Width <= 0 || bounds.Height <= 0) return;
        WindowPlacementStore.Save(WindowPlacementPath, new WindowPlacement(bounds.X, bounds.Y, bounds.Width, bounds.Height,
            WindowState == FormWindowState.Maximized || WindowState == FormWindowState.Minimized && _lastVisibleWindowState == FormWindowState.Maximized));
    }
}
