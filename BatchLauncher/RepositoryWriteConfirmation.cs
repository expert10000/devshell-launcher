namespace BatchLauncher;

internal static class RepositoryWriteConfirmation
{
    public static string? ConfirmCommit(IWin32Window owner, RepositoryWritePreview preview)
    {
        using var dialog = new Form { Text = "Commit staged changes", StartPosition = FormStartPosition.CenterParent,
            ClientSize = new Size(660, 540), MinimumSize = new Size(560, 500), MinimizeBox = false, MaximizeBox = false };
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(18), ColumnCount = 1, RowCount = 6 };
        layout.RowStyles.Add(new(SizeType.AutoSize)); layout.RowStyles.Add(new(SizeType.Percent, 50));
        layout.RowStyles.Add(new(SizeType.AutoSize)); layout.RowStyles.Add(new(SizeType.Percent, 50));
        layout.RowStyles.Add(new(SizeType.AutoSize)); layout.RowStyles.Add(new(SizeType.AutoSize));
        var caption = new Label { AutoSize = true, MaximumSize = new Size(610, 0), Margin = new Padding(0, 0, 0, 10),
            Text = $"{preview.Path}\r\nBranch: {preview.Branch}\r\n{preview.StagedCount} staged files. Only staged changes will be committed." };
        var files = new ListBox { Dock = DockStyle.Fill, HorizontalScrollbar = true };
        files.Items.AddRange(preview.StagedFiles.Cast<object>().ToArray());
        var message = new TextBox { Dock = DockStyle.Fill, Multiline = true, ScrollBars = ScrollBars.Vertical, MaxLength = 4000 };
        var warning = new Label { AutoSize = true, MaximumSize = new Size(610, 0), Text = "Unstaged and untracked files are not added. If the branch, HEAD, or index changes after this preview, the action is rejected." };
        var buttons = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft };
        var commit = new Button { Text = "Commit staged files", AutoSize = true, Enabled = false, DialogResult = DialogResult.OK };
        var cancel = new Button { Text = "Cancel", AutoSize = true, DialogResult = DialogResult.Cancel };
        message.TextChanged += (_, _) => commit.Enabled = !string.IsNullOrWhiteSpace(message.Text);
        buttons.Controls.Add(commit); buttons.Controls.Add(cancel);
        layout.Controls.Add(caption); layout.Controls.Add(files); layout.Controls.Add(new Label { Text = "Commit message", AutoSize = true });
        layout.Controls.Add(message); layout.Controls.Add(warning); layout.Controls.Add(buttons);
        dialog.Controls.Add(layout); dialog.CancelButton = cancel;
        return dialog.ShowDialog(owner) == DialogResult.OK ? message.Text.Trim() : null;
    }

    public static bool ConfirmPush(IWin32Window owner, RepositoryWritePreview preview) => MessageBox.Show(owner,
        $"Repository: {preview.Path}\r\nBranch: {preview.Branch}\r\nCommit: {preview.Head}\r\n\r\nRemote: {preview.Remote}\r\nDestination: {preview.RemoteDisplay}\r\nRemote branch: {preview.RemoteRef}\r\n\r\nPush this confirmed commit only?\r\nNo force-push, tag push, automatic commit, or upstream change.",
        "Confirm repository push", MessageBoxButtons.YesNo, MessageBoxIcon.Warning, MessageBoxDefaultButton.Button2) == DialogResult.Yes;
}
