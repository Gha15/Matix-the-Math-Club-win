using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using Microsoft.Web.WebView2.Core;

namespace MatixTheMathClub
{
    public partial class MainWindow : Window
    {
        private System.Windows.Forms.NotifyIcon? _tray;

        // remembered position/size so our custom maximize can restore properly
        private Rect _restoreBounds = Rect.Empty;
        private bool _isSnapMaximized;

        [DllImport("user32.dll")]
        private static extern bool ReleaseCapture();

        [DllImport("user32.dll")]
        private static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

        private const int WM_NCLBUTTONDOWN = 0x00A1;
        private const int HTCAPTION = 2;

        public MainWindow()
        {
            InitializeComponent();
            Loaded += OnLoaded;
            StateChanged += (s, e) => PushWindowState();
            Closed += (s, e) => { _tray?.Dispose(); };
        }

        private async void OnLoaded(object sender, RoutedEventArgs e)
        {
            var dataDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MatixTheMathClub");
            Directory.CreateDirectory(dataDir);
            var env = await CoreWebView2Environment.CreateAsync(null, dataDir);
            await Browser.EnsureCoreWebView2Async(env);
            var core = Browser.CoreWebView2;

            core.SetVirtualHostNameToFolderMapping("matix.local", AppContext.BaseDirectory, CoreWebView2HostResourceAccessKind.Allow);

            // camera + microphone for club video calls
            core.PermissionRequested += (s, args) => args.State = CoreWebView2PermissionState.Allow;

            // no right-click browser menu / no F12 devtools bar: it is an app, not a browser
            core.Settings.AreBrowserAcceleratorKeysEnabled = false;
            core.Settings.IsStatusBarEnabled = false;

            // window.open: club pages stay in-app, external links go to the browser
            core.NewWindowRequested += (s, args) =>
            {
                args.Handled = true;
                var uri = args.Uri ?? "";
                if (uri.StartsWith("https://matix.local", StringComparison.OrdinalIgnoreCase))
                {
                    core.Navigate(uri);
                }
                else if (uri.StartsWith("http", StringComparison.OrdinalIgnoreCase))
                {
                    Process.Start(new ProcessStartInfo(uri) { UseShellExecute = true });
                }
            };

            // messages from the page: window buttons, dragging, and notifications
            core.WebMessageReceived += (s, args) =>
            {
                string raw = "";
                try { raw = args.TryGetWebMessageAsString() ?? ""; }
                catch { try { raw = args.WebMessageAsJson ?? ""; } catch { } }
                OnWebMessage(raw);
            };

            core.NavigationCompleted += (s, args) => PushWindowState();

            core.Navigate("https://matix.local/app.html");
        }

        private void OnWebMessage(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw)) return;
            var msg = raw.Trim().Trim('"');

            // ---- window controls from the app's own title bar ----
            if (msg.StartsWith("matix:", StringComparison.OrdinalIgnoreCase))
            {
                var cmd = msg.Substring(6).ToLowerInvariant();
                Dispatcher.Invoke(() =>
                {
                    switch (cmd)
                    {
                        case "minimize":
                            WindowState = WindowState.Minimized;
                            break;
                        case "maximize":
                        case "togglemax":
                        case "restore":
                            ToggleMaximize();
                            break;
                        case "close":
                            Close();
                            break;
                        case "drag":
                            StartDrag();
                            break;
                    }
                });
                return;
            }

            // ---- notifications (unchanged behaviour) ----
            try
            {
                using var doc = System.Text.Json.JsonDocument.Parse(raw);
                var root = doc.RootElement;
                if (!root.TryGetProperty("type", out var t) || t.GetString() != "notify") return;
                var title = root.TryGetProperty("title", out var ti) ? (ti.GetString() ?? "") : "";
                var body = root.TryGetProperty("body", out var b) ? (b.GetString() ?? "") : "";
                ShowToast(string.IsNullOrWhiteSpace(title) ? "Matix the Math Club" : title, body);
            }
            catch { }
        }

        // Drag the window by holding the app's own title bar.
        // ReleaseCapture + NCLBUTTONDOWN is the reliable way to do this while
        // the mouse is captured by the WebView2 child window.
        private void StartDrag()
        {
            if (_isSnapMaximized || WindowState == WindowState.Maximized)
            {
                // dragging a maximized window restores it, like every other Windows app
                ToggleMaximize();
            }
            try
            {
                var helper = new WindowInteropHelper(this);
                ReleaseCapture();
                SendMessage(helper.Handle, WM_NCLBUTTONDOWN, (IntPtr)HTCAPTION, IntPtr.Zero);
            }
            catch
            {
                try { DragMove(); } catch { }
            }
        }

        // Custom maximize that fills the work area only, so a borderless window
        // never covers the Windows taskbar.
        private void ToggleMaximize()
        {
            if (WindowState == WindowState.Minimized) WindowState = WindowState.Normal;

            if (_isSnapMaximized)
            {
                if (_restoreBounds != Rect.Empty)
                {
                    Left = _restoreBounds.Left;
                    Top = _restoreBounds.Top;
                    Width = _restoreBounds.Width;
                    Height = _restoreBounds.Height;
                }
                _isSnapMaximized = false;
            }
            else
            {
                _restoreBounds = new Rect(Left, Top, Width, Height);
                var wa = SystemParameters.WorkArea;
                Left = wa.Left;
                Top = wa.Top;
                Width = wa.Width;
                Height = wa.Height;
                _isSnapMaximized = true;
            }
            PushWindowState();
        }

        // keep the page's maximize icon in sync (square vs restore)
        private void PushWindowState()
        {
            var isMax = _isSnapMaximized || WindowState == WindowState.Maximized;
            try
            {
                Browser?.CoreWebView2?.ExecuteScriptAsync(
                    "try{window.mxSetMaximized&&window.mxSetMaximized(" + (isMax ? "true" : "false") + ")}catch(e){}");
            }
            catch { }
        }

        private void ShowToast(string title, string body)
        {
            Dispatcher.Invoke(() =>
            {
                if (_tray == null)
                {
                    _tray = new System.Windows.Forms.NotifyIcon
                    {
                        Icon = System.Drawing.SystemIcons.Information,
                        Visible = true,
                        Text = "Matix the Math Club"
                    };
                }
                _tray.BalloonTipTitle = title;
                _tray.BalloonTipText = string.IsNullOrWhiteSpace(body) ? "Open the app to see it!" : body;
                _tray.ShowBalloonTip(6000);
            });
        }
    }
}
