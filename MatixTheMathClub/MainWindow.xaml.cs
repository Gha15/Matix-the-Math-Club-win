using System;
using System.Diagnostics;
using System.IO;
using System.Windows;
using Microsoft.Web.WebView2.Core;

namespace MatixTheMathClub
{
    public partial class MainWindow : Window
    {
        public MainWindow()
        {
            InitializeComponent();
            Loaded += OnLoaded;
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

            core.Navigate("https://matix.local/app.html");
        }
    }
}
