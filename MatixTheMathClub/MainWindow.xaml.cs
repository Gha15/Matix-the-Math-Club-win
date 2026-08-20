using System;
using System.Diagnostics;
using System.IO;
using System.Windows;
using Microsoft.Web.WebView2.Core;

namespace MatixTheMathClub
{
    public partial class MainWindow : Window
    {
        private System.Windows.Forms.NotifyIcon? _tray;

        public MainWindow()
        {
            InitializeComponent();
            Loaded += OnLoaded;
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

            // real Windows notifications from the club app
            core.WebMessageReceived += (s, args) =>
            {
                try { OnWebMessage(args.TryGetWebMessageAsString()); } catch { }
            };

            core.Navigate("https://matix.local/app.html");
        }

        private void OnWebMessage(string json)
        {
            try
            {
                using var doc = System.Text.Json.JsonDocument.Parse(json);
                var root = doc.RootElement;
                if (!root.TryGetProperty("type", out var t) || t.GetString() != "notify") return;
                var title = root.TryGetProperty("title", out var ti) ? (ti.GetString() ?? "") : "";
                var body = root.TryGetProperty("body", out var b) ? (b.GetString() ?? "") : "";
                ShowToast(string.IsNullOrWhiteSpace(title) ? "Matix the Math Club" : title, body);
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
