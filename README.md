# Matix the Math Club - Windows (C#)

This is an EXACT 1:1 copy of the club web app. The real `app.html` ships with
the program and runs inside a native C# WPF window through WebView2, so every
page, feature and pixel matches the original: login, workspace, AI, learn,
games hub, chat, ideas, points, notifications, roles, video calls, all of it.

## Open it
you can download [here](https://toffeeshare.com/c/M39-kYGdSI) if you wanna skip steps
1. Install the .NET 8 SDK (included with Visual Studio 2022 17.8+).
2. Open `Matix the Math Club.sln`, press F5. NuGet restores the WebView2
   package automatically on first build (needs internet once).
3. Or from a terminal: `dotnet run --project MatixTheMathClub`.

WebView2 Runtime: preinstalled on Windows 11 and almost all updated Windows 10
machines. If a machine somehow lacks it, install "WebView2 Evergreen Runtime"
from Microsoft once.

## How it works

- `MainWindow.xaml.cs` serves the bundled `app.html` from a private https
  origin (`matix.local`), so localStorage and sign-ins persist.
- Camera/microphone prompts from the page (video calls) are allowed natively.
- External links open in your default browser; the club stays in-app.
- Talks to your Firebase Realtime Database directly, exactly like the website.

## Updating the app when the HTML changes

Replace `MatixTheMathClub/app.html` with the new file and rebuild. Nothing
else to change.
