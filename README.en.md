# Elysia Tunnel GUI · Local model sharing

[简体中文](README.md) | English

[![Release](https://img.shields.io/github/v/release/FuFu-Flash/elysia-tunnel-gui?style=flat-square&color=C24C86)](https://github.com/FuFu-Flash/elysia-tunnel-gui/releases/latest)
[![Windows 10/11](https://img.shields.io/badge/Windows-10%20%2F%2011-0078D4?style=flat-square)](#download-and-run)
[![Architecture x64](https://img.shields.io/badge/architecture-x64-6A4C93?style=flat-square)](PACKAGING.md)

**Automatically discover local model APIs and share them with remote clients in one click.**

Let your local model answer remote requests. For example, run a model in [Strata](https://github.com/Niko1221/Strata), automatically discover and share its API with **Elysia Tunnel**, then connect [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/deepseek-harness) to that address. The model keeps running on your computer; the remote client sends requests through the shared API.

This Windows app supports Cloudflare / FRP, multiple tunnels, and background operation in the system tray. It can also share a local website or another HTTP service by its port.

**[Download ElysiaTunnel.exe](https://github.com/FuFu-Flash/elysia-tunnel-gui/releases/latest/download/ElysiaTunnel.exe)** · [Strata + DSH walkthrough](#strata-dsh-tutorial) · [Latest release](https://github.com/FuFu-Flash/elysia-tunnel-gui/releases/latest)

![Automatic local model discovery and sharing](docs/model-sharing.png)

## Download and run

Download `ElysiaTunnel.exe` and double-click it. The Windows 10 / 11 x64 package includes Python, Qt, Cloudflare, and FRP tunnel engines, so there are no separate dependencies to install. The single-file executable extracts its runtime at startup; give it a moment to open. Establishing a tunnel requires an internet connection.

The v0.4.0 EXE is about 75.33 MiB. The release also includes a `.sha256` file to verify your download.

<a id="strata-dsh-tutorial"></a>

## Illustrated walkthrough: Strata → Elysia → DeepSeek Harness

This walkthrough uses Strata as the model server and DSH as the remote client. Complete **steps 1–3 on the computer running the model**, then **step 4 on the computer running DSH**. Strata and DSH are separate applications to install for this example.

The screenshots show real interfaces with demonstration data: `local-model` is a placeholder model ID, and `https://your-tunnel.example/v1` is an example address that cannot be used. Use your own detected model and public address. The DSH screenshots use **0.2.0-rc.2**; later versions may have different menus.

**Choose a suitable transport first.** DSH 0.2.0-rc.2 has no switch to disable streaming, so this walkthrough uses configured FRP or a Cloudflare fixed domain. Cloudflare documents that [Quick Tunnels do not support SSE](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/#limitations). Temporary addresses work with Elysia's **Copy example** Python code for non-streaming requests; use another transport for DSH streaming. Public model sharing through FRP or a fixed domain has not yet been tested here.

### 1. Start the model in Strata

Follow [Strata's setup instructions](https://github.com/Niko1221/Strata#install). On Windows, double-click `START-HERE.bat`, wait for the model to load, and open `http://127.0.0.1:8080`. Select **About** to check the API address and model name. If you changed the port, use your own port in the following steps. Strata's project documents its installation, model downloads, and hardware requirements.

Before public sharing, set a non-empty `api_key` in Strata's current model configuration (`strata-<model>.json`) and restart the service; see its [configuration notes](https://github.com/Niko1221/Strata/blob/main/docs/INSTALL.md#where-things-are-stored). Keep the service listening on `127.0.0.1`; Elysia forwards that local service. The **API key** field on Strata's web page lets the browser connect to the server. It does not configure server authentication.

![Strata About page: check the local API address](docs/tutorial/strata-about.png)

*Strata interface demonstration. Confirm that your own model service is ready before continuing; the pictured model and runtime data are placeholders.*

### 2. Detect the service and start sharing

Open Elysia Tunnel's **Model sharing** page. The app automatically looks for local model APIs. A service with a key may initially show **Verify first**: enter Strata's port (default `8080`) and its key in **Existing model server API key**, then click **Detect port**. Once the model list is available, select the service and model. Use **Scan again** if you started Strata after opening the page.

![Automatically detect Strata's model API](docs/tutorial/elysia-detect.png)

*Detection interface demonstration. Model names come from the service's actual list. Detection only reads that list; it does not load models or run inference, and the detection key is not saved.*

Choose your transport, then click **Start sharing ♪**. For **Fixed domain**, open **Settings**, choose **Fixed domain** in the address options, authorize your account, and bind your domain. This requires your own domain managed by Cloudflare. For **FRP**, configure your own FRPS server and enter the remote forwarding port. Detection alone does not make the service public.

### 3. Copy the client address and model ID

Once connected, click **Copy Base URL** and **Copy model ID** under **Client connection**. The Base URL must include its final `/v1`, as in `https://your-tunnel.example/v1`. Copy the actual model ID rather than the screenshot's `local-model` placeholder.

![Copy the model API address and model ID](docs/tutorial/elysia-share.png)

*Connection information demonstration. The domain and connected status are examples; use your own address after connecting. The remote client cannot use the model computer's `127.0.0.1:8080`.*

### 4. Connect DeepSeek Harness

Install and open [DeepSeek Harness](https://www.deepseek.com/en/download/). In the bottom-left menu, open **More → Settings → Models**, click **Add model provider**, and choose **Custom model API**. Fill in the form:

| DSH field | What to enter |
| --- | --- |
| Provider ID | For example, `strata-remote`; start with a lowercase letter and use only lowercase letters, digits, and hyphens |
| Display name | A name such as `Strata` |
| API protocol | **OpenAI Chat Completions** |
| Base URL | The public address copied from Elysia, ending in `/v1` |
| API key | The real key configured in Strata in step 1 |
| Model ID | The ID copied in step 3, or a model selected after fetching the list |

![DeepSeek Harness custom model provider configuration](docs/tutorial/dsh-provider.png)

*DSH configuration demonstration. Replace the example address and enter your own Strata API key. Choose Chat Completions for this walkthrough, rather than OpenAI Responses or Anthropic.*

Click **Fetch available models**, select your model, and click **Add selected**. If DSH cannot fetch the list, use **Add model** and paste the exact model ID copied in step 3. Finish with **Create provider**.

Return to the conversation, click the current model name at the bottom of the message box, and open the model list to select the newly added Strata model.

![Select the newly added Strata model in DSH](docs/tutorial/dsh-model.png)

Send a short message to check the connection, such as “Reply with exactly OK. Do not call any tools.” Keep Strata and Elysia running while using the client.

![DSH conversation demonstration](docs/tutorial/dsh-chat.png)

*DSH conversation demonstration using a local test service; this is not a new public Strata test. See “What has been checked” below for the earlier real DSH request.*

Click **Stop sharing** or exit Elysia to end remote access through this tunnel. A temporary address changes when reconnected; a fixed domain uses the domain you configured.

Choosing a model selects it for the client example. Sharing exposes the entire service port, so other models and HTTP paths may also be accessible. A detection key does not add authentication to your model server. Configure access control when using other services, too; [Ollama's local API does not require authentication](https://docs.ollama.com/api/authentication).

## Share a local website

Want to show a friend the website running on your computer without digging through commands? Enter its port, click **Start tunnel**, wait for the public address, and send it over.

1. Start your local website or application and check that it works on this computer.
2. Open **Tunnels**, choose its protocol, and enter the local port. For `http://localhost:8080`, choose HTTP and enter `8080`.
3. Click **Start tunnel** and copy the public address once connected. Cloudflare temporary addresses require no account or domain.

Stopping the tunnel ends access through that public address. Reconnecting creates a new temporary address.

![Tunnels](docs/screenshot.png)

## Everyday use

- **Manage several tunnels.** Give each its own name and port, check its address and logs, and start or stop them individually or together.
- **Keep running in the tray.** Closing the window hides it in the system tray. Choose **Exit** to stop every tunnel and close the app.
- **Save your FRPS servers.** Keep several server profiles and choose one for each tunnel. Cloudflare tunnels share one account.
- **Detect local ports and read live logs.** Find listening ports, copy public addresses, and stop or restart connections.
- **Elysia pink, themes, and button ripples.** Adjust the theme and animation speed in Settings, or disable animations. The window has a top control area without title text and supports dragging, resizing, maximizing, and restoring.
- **简体中文 / English.** Switch the interface language instantly; your choice is saved. Raw tunnel-engine logs remain in their original language.
- **Adapt to window size.** Wide windows show controls and status side by side. Narrow windows use a scrolling single column. Settings opens with a smooth transition.

![Settings](docs/settings.png)

## Tunnel options

| Option | Use | What you need |
| --- | --- | --- |
| Cloudflare temporary address | Temporarily share HTTP / HTTPS services; use non-streaming requests for model APIs | A running local service and an internet connection |
| Cloudflare fixed domain | Give your service a stable address on your own domain | A Cloudflare-managed domain, account authorization, and a bound tunnel |
| FRP | Forward TCP ports through your own server | FRPS configuration and an accessible remote forwarding port |
| Auto mode | Prefer Cloudflare for HTTP / HTTPS, with configured FRP as a fallback | The configuration required for each transport |

Fixed-domain mode does not silently switch to a temporary address. Real Cloudflare account authorization, named tunnel creation, DNS binding, and fixed-domain connectivity remain untested. See the [fixed-domain notes in Chinese](docs/cloudflare-fixed-domain.md). Real FRPS forwarding also remains untested. FRP model sharing currently uses unencrypted HTTP for public access.

Tunnel configurations are saved locally for next time, but connections do not start automatically. Saved FRPS tokens use Windows user-level encryption.

## What has been checked

Local Windows 11 checks cover language switching, Settings navigation and return, independent tunnel-process management, FRPS profile switching, tray behavior, and cleanup on exit. Interaction checks cover button ripples, keyboard input, animation speed, and disabling animations. Window checks cover resizing without shifting the top-left position, maximizing to the screen's work area, and restoring the original position and size.

Model discovery and sharing checks cover reading model lists, detection-key handling, copying client addresses and examples, preserving existing tunnel configurations, HTTP forwarding, and cleanup. This round used a Cloudflare temporary address to read a Strata server's model list publicly and complete one non-streaming request. The actual DeepSeek Harness (DSH) Windows client also fetched models and completed one short reply.

One successful DSH request does not establish general SSE streaming support on Quick Tunnels or verify every model, client, or long-running session. Windows 10, real FRPS forwarding, Cloudflare account and fixed-domain operations, HTTPS origin certificates, and long-running stability remain unverified.

The current EXE was launched in an isolated environment with only the system PATH and no preinstalled Python or Qt. Checks covered the model page with animations disabled, local model API detection, Settings navigation, window resizing, and exit. Bundled source, UI resources, and both engines passed verification. At this computer's 150% display scale, the maximized client area exactly matched the screen's work area. See the [packaging notes in Chinese](PACKAGING.md) for the build process and the [animation measurements in Chinese](docs/animation-performance.md) for the devices and test scope.

## Run or build from source

Keep the full project directory, install its dependencies, and launch the app:

```powershell
python -m pip install -r requirements.txt
pythonw tunnel_gui.pyw
```

When running from source, missing tunnel engines are downloaded from their official releases and checked with SHA-256. Release executables include the engines; the source repository does not contain their binaries. Account certificates, tunnel credentials, and personal settings are not distributed with the repository or executable.

See [packaging notes in Chinese](PACKAGING.md) for build instructions, dependency versions, and verification.

## Credits

Thanks to [FRP](https://github.com/fatedier/frp) and [Cloudflare Tunnel](https://github.com/cloudflare/cloudflared) for the connection engines. The settings icon comes from Google's official [Material Symbols](https://github.com/google/material-design-icons). Window controls use the official [QWindowKit](https://github.com/stdware/qwindowkit) QML example and icons, adapted to the app's theme.

Third-party licenses and source references are included in `third_party_licenses`, `assets/icons`, and `qml/vendor/qwindowkit`, and bundled with the executable.
