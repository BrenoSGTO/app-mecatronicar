using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;

[assembly: AssemblyTitle("MecatroniCar")]
[assembly: AssemblyDescription("MecatroniCar - Sistema de Histórico de Veículos da Oficina Mecânica")]
[assembly: AssemblyCompany("MecatroniCar Oficina Mecânica")]
[assembly: AssemblyProduct("MecatroniCar")]
[assembly: AssemblyCopyright("Copyright © 2026 MecatroniCar")]
[assembly: AssemblyVersion("1.0.7.0")]
[assembly: AssemblyFileVersion("1.0.7.0")]
[assembly: ComVisible(false)]

internal static class Program
{
    [DllImport("shell32.dll", SetLastError = true)]
    private static extern int SetCurrentProcessExplicitAppUserModelID([MarshalAs(UnmanagedType.LPWStr)] string AppID);

    private static bool IsWorkingPython(string exePath)
    {
        if (string.IsNullOrEmpty(exePath)) return false;
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

    private static string FindPythonExecutable()
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

        // Check PATH entries
        string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string dir in pathEnv.Split(';'))
        {
            string trimmed = dir.Trim();
            if (string.IsNullOrEmpty(trimmed)) continue;
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

    private static void EnsureDependencies(string pythonExe, string appDir)
    {
        try
        {
            ProcessStartInfo checkPsi = new ProcessStartInfo();
            checkPsi.FileName = pythonExe;
            checkPsi.Arguments = "-c \"import flask, openpyxl, xlrd\"";
            checkPsi.WorkingDirectory = appDir;
            checkPsi.CreateNoWindow = true;
            checkPsi.UseShellExecute = false;
            using (Process p = Process.Start(checkPsi))
            {
                if (p != null && p.WaitForExit(8000) && p.ExitCode == 0)
                    return;
            }

            ProcessStartInfo pipPsi = new ProcessStartInfo();
            pipPsi.FileName = pythonExe;
            pipPsi.Arguments = "-m pip install --disable-pip-version-check --quiet openpyxl xlrd flask";
            pipPsi.WorkingDirectory = appDir;
            pipPsi.CreateNoWindow = true;
            pipPsi.UseShellExecute = false;
            using (Process pipProc = Process.Start(pipPsi))
            {
                if (pipProc != null) pipProc.WaitForExit(90000);
            }
        }
        catch { }
    }

    [STAThread]
    static void Main()
    {
        try
        {
            try { SetCurrentProcessExplicitAppUserModelID("MecatroniCar.Oficina.App.1"); } catch { }
            string appDir = Path.GetDirectoryName(Application.ExecutablePath);
            string pythonPath = FindPythonExecutable();

            if (string.IsNullOrEmpty(pythonPath))
            {
                MessageBox.Show(
                    "O motor Python não foi encontrado neste computador.\n\n" +
                    "Por favor, execute novamente o 'Instalar-MecatroniCar.exe' para que ele instale e configure automaticamente todos os componentes necessários.",
                    "MecatroniCar - Componente Ausente",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning
                );
                return;
            }

            EnsureDependencies(pythonPath, appDir);

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = pythonPath;
            psi.Arguments = "app.py";
            psi.WorkingDirectory = appDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            Process.Start(psi);
        }
        catch (Exception ex)
        {
            MessageBox.Show("Não foi possível iniciar o MecatroniCar:\n" + ex.Message, "MecatroniCar", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}

