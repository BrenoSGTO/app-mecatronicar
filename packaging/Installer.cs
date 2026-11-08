using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;


internal class InstallerForm : Form
{
    private string targetDir;
    private CheckBox chkDesktop;
    private Button btnInstall;
    private Button btnCancel;
    private ProgressBar progressBar;
    private Label lblStatus;
    private TextBox txtPath;

    public InstallerForm()
    {
        InitializeComponents();
    }

    private void InitializeComponents()
    {
        this.Text = "Instalador - MecatroniCar";
        this.Size = new Size(520, 380);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.StartPosition = FormStartPosition.CenterScreen;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.BackColor = Color.FromArgb(248, 250, 252);
        this.Font = new Font("Segoe UI", 9F, FontStyle.Regular);

        // Header Panel
        Panel headerPanel = new Panel();
        headerPanel.Dock = DockStyle.Top;
        headerPanel.Height = 85;
        headerPanel.BackColor = Color.FromArgb(17, 24, 39); // Slate-900

        // Yellow line under header
        Panel yellowLine = new Panel();
        yellowLine.Dock = DockStyle.Bottom;
        yellowLine.Height = 4;
        yellowLine.BackColor = Color.FromArgb(249, 204, 1); // Brand yellow
        headerPanel.Controls.Add(yellowLine);

        Label lblTitle = new Label();
        lblTitle.Text = "MecatroniCar";
        lblTitle.Font = new Font("Segoe UI", 16F, FontStyle.Bold);
        lblTitle.ForeColor = Color.FromArgb(249, 204, 1);
        lblTitle.Location = new Point(20, 16);
        lblTitle.AutoSize = true;
        headerPanel.Controls.Add(lblTitle);

        Label lblSub = new Label();
        lblSub.Text = "Instalador do Sistema de Histórico da Oficina Mecânica";
        lblSub.Font = new Font("Segoe UI", 9.5F, FontStyle.Regular);
        lblSub.ForeColor = Color.FromArgb(156, 163, 175);
        lblSub.Location = new Point(22, 48);
        lblSub.AutoSize = true;
        headerPanel.Controls.Add(lblSub);

        this.Controls.Add(headerPanel);

        // Target path
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        targetDir = Path.Combine(localAppData, "Programs", "MecatroniCar");

        // Body Elements
        Label lblDest = new Label();
        lblDest.Text = "O MecatroniCar será instalado no seguinte local do computador:";
        lblDest.Location = new Point(22, 105);
        lblDest.AutoSize = true;
        lblDest.ForeColor = Color.FromArgb(30, 41, 59);
        this.Controls.Add(lblDest);

        txtPath = new TextBox();
        txtPath.Text = targetDir;
        txtPath.Location = new Point(22, 128);
        txtPath.Width = 460;
        txtPath.ReadOnly = true;
        txtPath.BackColor = Color.FromArgb(241, 245, 249);
        this.Controls.Add(txtPath);

        // Checkbox for Desktop shortcut
        chkDesktop = new CheckBox();
        chkDesktop.Text = "Adicionar um atalho na Área de Trabalho";
        chkDesktop.Checked = true;
        chkDesktop.Font = new Font("Segoe UI", 9.5F, FontStyle.Bold);
        chkDesktop.ForeColor = Color.FromArgb(15, 23, 42);
        chkDesktop.Location = new Point(22, 168);
        chkDesktop.AutoSize = true;
        chkDesktop.Cursor = Cursors.Hand;
        this.Controls.Add(chkDesktop);

        // Progress bar
        progressBar = new ProgressBar();
        progressBar.Location = new Point(22, 210);
        progressBar.Width = 460;
        progressBar.Height = 16;
        progressBar.Visible = false;
        this.Controls.Add(progressBar);

        // Status label
        lblStatus = new Label();
        lblStatus.Text = "Pronto para instalar. Clique no botão abaixo para iniciar.";
        lblStatus.Location = new Point(22, 235);
        lblStatus.Width = 460;
        lblStatus.Height = 35;
        lblStatus.ForeColor = Color.FromArgb(100, 116, 139);
        this.Controls.Add(lblStatus);

        // Bottom buttons
        btnInstall = new Button();
        btnInstall.Text = "🚀 Instalar e Abrir";
        btnInstall.Location = new Point(290, 280);
        btnInstall.Size = new Size(190, 42);
        btnInstall.BackColor = Color.FromArgb(249, 204, 1);
        btnInstall.ForeColor = Color.FromArgb(17, 24, 39);
        btnInstall.Font = new Font("Segoe UI", 10F, FontStyle.Bold);
        btnInstall.FlatStyle = FlatStyle.Flat;
        btnInstall.FlatAppearance.BorderSize = 0;
        btnInstall.Cursor = Cursors.Hand;
        btnInstall.Click += BtnInstall_Click;
        this.Controls.Add(btnInstall);

        btnCancel = new Button();
        btnCancel.Text = "Cancelar";
        btnCancel.Location = new Point(190, 280);
        btnCancel.Size = new Size(90, 42);
        btnCancel.BackColor = Color.FromArgb(226, 232, 240);
        btnCancel.ForeColor = Color.FromArgb(71, 85, 105);
        btnCancel.Font = new Font("Segoe UI", 9.5F, FontStyle.Regular);
        btnCancel.FlatStyle = FlatStyle.Flat;
        btnCancel.FlatAppearance.BorderSize = 0;
        btnCancel.Cursor = Cursors.Hand;
        btnCancel.Click += (s, e) => this.Close();
        this.Controls.Add(btnCancel);
    }

    private bool IsWorkingPython(string exePath)
    {
        if (string.IsNullOrEmpty(exePath)) return false;
        if (exePath.IndexOf("WindowsApps", StringComparison.OrdinalIgnoreCase) >= 0) return false;
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = exePath;
            psi.Arguments = "-c \"import sys; sys.exit(0)\"";
            psi.CreateNoWindow = true;
            psi.UseShellExecute = false;
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            using (Process p = Process.Start(psi))
            {
                if (p == null) return false;
                if (!p.WaitForExit(5000)) return false;
                return p.ExitCode == 0;
            }
        }
        catch
        {
            return false;
        }
    }

    private string FindPythonExecutable()
    {
        List<string> searchRoots = new List<string>();
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (!string.IsNullOrEmpty(localAppData))
            searchRoots.Add(Path.Combine(localAppData, "Programs", "Python"));

        string progFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        if (!string.IsNullOrEmpty(progFiles))
            searchRoots.Add(progFiles);

        string progFiles86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        if (!string.IsNullOrEmpty(progFiles86))
            searchRoots.Add(progFiles86);

        searchRoots.Add(@"C:\");

        foreach (string root in searchRoots)
        {
            try
            {
                if (!Directory.Exists(root)) continue;
                string[] dirs = Directory.GetDirectories(root, "Python3*");
                Array.Sort(dirs);
                Array.Reverse(dirs);
                foreach (string d in dirs)
                {
                    string candidate = Path.Combine(d, "python.exe");
                    if (File.Exists(candidate) && IsWorkingPython(candidate))
                        return candidate;
                }
            }
            catch { }
        }

        string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string dir in pathEnv.Split(';'))
        {
            string trimmed = dir.Trim();
            if (string.IsNullOrEmpty(trimmed)) continue;
            if (trimmed.IndexOf("WindowsApps", StringComparison.OrdinalIgnoreCase) >= 0) continue;
            try
            {
                string candidate = Path.Combine(trimmed, "python.exe");
                if (File.Exists(candidate) && IsWorkingPython(candidate))
                    return candidate;
            }
            catch { }
        }

        if (IsWorkingPython("python.exe"))
            return "python.exe";

        return null;
    }

    private string DownloadAndInstallPython()
    {
        ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
        string pyUrl = Environment.Is64BitOperatingSystem
            ? "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
            : "https://www.python.org/ftp/python/3.12.8/python-3.12.8.exe";

        string tempInstaller = Path.Combine(Path.GetTempPath(), "python-3.12.8-installer.exe");

        UpdateStatus("Baixando motor Python para este computador (1ª instalação)...", 52);

        HttpWebRequest req = (HttpWebRequest)WebRequest.Create(pyUrl);
        req.UserAgent = "MecatroniCar-Installer";
        req.Timeout = 30000;
        using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
        using (Stream netStream = resp.GetResponseStream())
        using (FileStream fileStream = new FileStream(tempInstaller, FileMode.Create, FileAccess.Write, FileShare.None))
        {
            long totalBytes = resp.ContentLength;
            byte[] buffer = new byte[32768];
            long downloaded = 0;
            int read;
            while ((read = netStream.Read(buffer, 0, buffer.Length)) > 0)
            {
                fileStream.Write(buffer, 0, read);
                downloaded += read;
                if (totalBytes > 0)
                {
                    int pct = 52 + (int)((downloaded / (double)totalBytes) * 14);
                    int dlPct = (int)((downloaded / (double)totalBytes) * 100);
                    UpdateStatus("Baixando motor Python (" + dlPct + "%)...", pct);
                }
            }
        }

        UpdateStatus("Instalando motor Python no computador (aguarde ~1 minuto)...", 68);
        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = tempInstaller;
        psi.Arguments = "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_doc=0 SimpleInstall=1";
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        using (Process p = Process.Start(psi))
        {
            if (p != null) p.WaitForExit(300000);
        }

        try { File.Delete(tempInstaller); } catch { }

        return FindPythonExecutable();
    }

    private void BtnInstall_Click(object sender, EventArgs e)
    {
        btnInstall.Enabled = false;
        btnCancel.Enabled = false;
        chkDesktop.Enabled = false;
        progressBar.Visible = true;
        progressBar.Value = 10;

        bool createDesktopShortcut = chkDesktop.Checked;

        Thread worker = new Thread(() =>
        {
            try
            {
                UpdateStatus("Criando diretório de instalação...", 15);
                Directory.CreateDirectory(targetDir);

                UpdateStatus("Extraindo arquivos do aplicativo...", 25);
                Assembly asm = Assembly.GetExecutingAssembly();
                using (Stream stream = asm.GetManifestResourceStream("MecatroniCar.Package"))
                {
                    if (stream == null)
                    {
                        throw new Exception("Pacote de instalação interno não encontrado no executável.");
                    }

                    using (ZipArchive zip = new ZipArchive(stream, ZipArchiveMode.Read))
                    {
                        int count = 0;
                        int total = zip.Entries.Count;
                        foreach (ZipArchiveEntry entry in zip.Entries)
                        {
                            count++;
                            string entryName = entry.FullName;
                            if (entryName.StartsWith("MecatroniCar/", StringComparison.OrdinalIgnoreCase))
                            {
                                entryName = entryName.Substring(13);
                            }
                            if (string.IsNullOrEmpty(entryName)) continue;

                            string destPath = Path.Combine(targetDir, entryName.Replace('/', Path.DirectorySeparatorChar));

                            if (entry.FullName.EndsWith("/"))
                            {
                                Directory.CreateDirectory(destPath);
                                continue;
                            }

                            Directory.CreateDirectory(Path.GetDirectoryName(destPath));

                            if (File.Exists(destPath) && (entryName.Equals("config.json", StringComparison.OrdinalIgnoreCase) || entryName.Equals("oficina_cache.db", StringComparison.OrdinalIgnoreCase)))
                            {
                                continue;
                            }

                            entry.ExtractToFile(destPath, true);

                            int pct = 25 + (int)((count / (float)total) * 25);
                            UpdateStatus("Instalando: " + Path.GetFileName(destPath), pct);
                        }
                    }
                }

                UpdateStatus("Verificando motor Python no computador...", 50);
                string pythonExe = FindPythonExecutable();
                if (string.IsNullOrEmpty(pythonExe))
                {
                    pythonExe = DownloadAndInstallPython();
                }

                if (string.IsNullOrEmpty(pythonExe))
                {
                    throw new Exception("Não foi possível instalar ou localizar o Python automaticamente. Verifique a conexão com a internet e tente novamente.");
                }

                UpdateStatus("Instalando bibliotecas do sistema (Flask, Excel)...", 78);
                try
                {
                    ProcessStartInfo pipInfo = new ProcessStartInfo();
                    pipInfo.FileName = pythonExe;
                    pipInfo.Arguments = "-m pip install --disable-pip-version-check --quiet openpyxl xlrd flask";
                    pipInfo.WorkingDirectory = targetDir;
                    pipInfo.CreateNoWindow = true;
                    pipInfo.UseShellExecute = false;
                    using (Process p = Process.Start(pipInfo))
                    {
                        if (p != null) p.WaitForExit(120000);
                    }
                }
                catch (Exception) { }

                UpdateStatus("Inicializando banco de dados e módulos...", 88);
                try
                {
                    ProcessStartInfo initInfo = new ProcessStartInfo();
                    initInfo.FileName = pythonExe;
                    initInfo.Arguments = "-c \"import cache, config, parser, server, updater; cache.init_db()\"";
                    initInfo.WorkingDirectory = targetDir;
                    initInfo.CreateNoWindow = true;
                    initInfo.UseShellExecute = false;
                    using (Process p = Process.Start(initInfo))
                    {
                        if (p != null) p.WaitForExit(15000);
                    }
                }
                catch (Exception) { }

                // Create Desktop Shortcut if checked
                if (createDesktopShortcut)
                {
                    UpdateStatus("Criando atalho na Área de Trabalho...", 94);
                    string desktopDir = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                    string shortcutPath = Path.Combine(desktopDir, "MecatroniCar - Oficina.lnk");
                    CreateShortcut(shortcutPath, Path.Combine(targetDir, "MecatroniCar.exe"), Path.Combine(targetDir, "app_icon.ico"));
                }

                // Create Start Menu Shortcut
                try
                {
                    string startMenu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.StartMenu), "Programs");
                    string startShortcut = Path.Combine(startMenu, "MecatroniCar.lnk");
                    CreateShortcut(startShortcut, Path.Combine(targetDir, "MecatroniCar.exe"), Path.Combine(targetDir, "app_icon.ico"));
                }
                catch (Exception) { }

                UpdateStatus("Instalação concluída! Abrindo o MecatroniCar...", 100);
                Thread.Sleep(800);

                // Start the application
                string appExe = Path.Combine(targetDir, "MecatroniCar.exe");
                if (File.Exists(appExe))
                {
                    Process.Start(new ProcessStartInfo(appExe) { WorkingDirectory = targetDir, UseShellExecute = true });
                }
                else
                {
                    Process.Start(new ProcessStartInfo(pythonExe, "app.py") { WorkingDirectory = targetDir, UseShellExecute = false, CreateNoWindow = true });
                }

                this.Invoke((MethodInvoker)delegate
                {
                    this.Close();
                });
            }
            catch (Exception ex)
            {
                this.Invoke((MethodInvoker)delegate
                {
                    progressBar.Visible = false;
                    btnInstall.Enabled = true;
                    btnCancel.Enabled = true;
                    chkDesktop.Enabled = true;
                    lblStatus.Text = "Erro na instalação: " + ex.Message;
                    MessageBox.Show("Erro durante a instalação:\n" + ex.Message, "Instalador MecatroniCar", MessageBoxButtons.OK, MessageBoxIcon.Error);
                });
            }
        });

        worker.IsBackground = true;
        worker.Start();
    }

    private void UpdateStatus(string message, int progress)
    {
        if (this.IsDisposed) return;
        this.Invoke((MethodInvoker)delegate
        {
            lblStatus.Text = message;
            progressBar.Value = Math.Min(100, Math.Max(0, progress));
        });
    }

    private void CreateShortcut(string shortcutPath, string targetPath, string iconPath)
    {
        try
        {
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            dynamic shell = Activator.CreateInstance(shellType);
            dynamic shortcut = shell.CreateShortcut(shortcutPath);
            shortcut.TargetPath = targetPath;
            shortcut.WorkingDirectory = Path.GetDirectoryName(targetPath);
            shortcut.Description = "MecatroniCar - Histórico de Veículos da Oficina Mecânica";
            if (File.Exists(iconPath))
            {
                shortcut.IconLocation = iconPath + ",0";
            }
            shortcut.Save();
        }
        catch (Exception ex)
        {
            Debug.WriteLine("Erro ao criar atalho: " + ex.Message);
        }
    }
}

internal static class ProgramInstaller
{
    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new InstallerForm());
    }
}
