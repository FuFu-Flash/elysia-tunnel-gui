# Elysia Tunnel GUI

[简体中文](README.md) | English

Want to show a friend the little website running on your computer, without digging through a pile of commands? That's what this app is for.

Enter the local port, click **Start tunnel**, wait for the public address, and send it over.

![Main window](docs/screenshot.png)

## Download and run

Download `ElysiaTunnel.exe` from [Releases](https://github.com/FuFu-Flash/elysia-tunnel-gui/releases) and double-click it. The Windows 10 / 11 x64 package includes Python, Qt, and both tunnel engines, so there's no separate environment to set up. The single-file executable extracts its runtime when starting; give it a moment to open.

Start your local service first. If it is available at `http://localhost:8080`, select HTTP, enter `8080`, and click **Start tunnel**. Establishing a tunnel requires an internet connection.

## A few things to make life easier

- **Run several tunnels at once.** Give each its own name and port, check its address and logs, and start or stop them individually or together.
- **Keep working in the tray.** Closing the window hides it in the system tray. Choose **Exit** to stop every tunnel and close the app.
- **Save your FRPS servers.** Keep several server profiles and choose one for each tunnel. Cloudflare tunnels share one account.
- **Elysia pink and button ripples.** Change the theme or animation speed in Settings, or choose **Disable animations**. On Windows 11, the title bar follows the theme with a light background.
- **简体中文 / English.** Switch the interface language instantly; your choice is saved. Raw tunnel-engine logs remain in their original language.
- **Side-by-side layout.** Connection controls and status sit next to each other, with smooth transitions to Settings. Smaller windows can still scroll to reach all controls.

![Settings](docs/settings.png)

## Tunnel options

- **Cloudflare temporary address:** Share a local HTTP / HTTPS service. The public address may change after a restart.
- **Cloudflare fixed domain:** Authorize through your browser, create a named tunnel, and bind your own domain. This requires a domain managed by Cloudflare and the necessary account permissions. Real account authorization, tunnel creation, DNS binding, and fixed-domain connectivity have not been verified end to end. See the [fixed-domain notes in Chinese](docs/cloudflare-fixed-domain.md).
- **FRP:** Connect to your own FRPS server for TCP port forwarding. You need the server configuration and an accessible remote forwarding port.
- **Auto mode:** Prefer Cloudflare for HTTP / HTTPS, with configured FRP available as a fallback. Fixed-domain mode does not silently switch to a temporary address.

The app can detect local listening ports, show live logs, copy public addresses, and stop or restart connections. Tunnel configurations are saved locally for next time, but connections do not start automatically. Saved FRPS tokens use Windows user-level encryption.

Before sharing a service, make sure it has suitable access protection. The app does not disable your system's security protections.

## What has been checked

Local Windows 11 checks cover Settings navigation and return, language switching, independent tunnel-process management, FRPS profile switching, tray hiding, and cleanup on exit. Ripple tests cover the press position, rounded clipping, keyboard input, repeated clicks, animation speed, and disabling animations. The packaged executable has been launched in an isolated environment, and its bundled engines have passed checksum verification.

A Cloudflare temporary tunnel was previously tested through a public connection; that network test was not repeated for this interface update. Multi-tunnel tests used local test processes and do not establish that real FRPS forwarding works. Windows 10, real Cloudflare account and fixed-domain operations, HTTPS origin certificates, and long-running stability remain unverified.

See the [animation measurements in Chinese](docs/animation-performance.md) for the devices and test scope. These results do not represent testing on every display or driver.

## Run or build from source

Keep the full project directory, install the dependencies from `requirements.txt`, and launch `pythonw tunnel_gui.pyw`. When running from source, missing tunnel engines are downloaded from their official releases and checked with SHA-256.

See [packaging notes in Chinese](PACKAGING.md) for build instructions and dependency versions. Release executables include the engines; the source repository does not contain their binaries. Account certificates, tunnel credentials, and personal settings are not distributed with the repository or executable.

The entry point is `tunnel_gui.pyw`. The interface lives in `qt_ui.py` and `qml/`; `tunnel_manager.py` manages multiple tunnels, `tunnel_core.py` handles engine processes, `profile_store.py` saves configurations, `tray_shell.py` provides tray controls, and `cloudflare_account.py` handles account and fixed-domain operations. The old Tk interface remains for historical tests.

Thanks to [FRP](https://github.com/fatedier/frp) and [Cloudflare Tunnel](https://github.com/cloudflare/cloudflared) for the connection engines. Third-party licenses and source references are included in `third_party_licenses` and bundled with the executable.

Get your local service ready, and let's head out together. ♪
