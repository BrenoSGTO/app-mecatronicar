using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    static void Main()
    {
        try
        {
            string appDir = Path.GetDirectoryName(Application.ExecutablePath);
            
            // Check python path
            string pythonPath = "python.exe";
            
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
            MessageBox.Show("Não foi possível iniciar o MecatroniCar:\n" + ex.Message + "\n\nVerifique se o Python está instalado neste computador.", "MecatroniCar", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
