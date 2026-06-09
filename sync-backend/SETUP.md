# MoroTracker cloud sync — setup

Goal: your tracker data lives on a free, always-on cloud VM that is reachable
**only from your own Tailscale tailnet**, over HTTPS, with no passwords. Every
device that has Tailscale running syncs automatically; any device without it
falls back to localStorage and keeps working offline.

```
 phone / laptop ──HTTPS──> https://moro.<tailnet>.ts.net ──> server.py ──> moro-state.json
 (on tailnet)              (Tailscale Serve, port 443)       (127.0.0.1:8787)
```

---

## 1. Create the free VM (Google Cloud)

1. In the GCP console → **Compute Engine → VM instances → Create instance**.
2. Pick the **always-free** shape:
   - Series **E2**, machine type **e2-micro**.
   - Region **us-central1**, **us-west1**, or **us-east1** (only these are free).
   - Boot disk: Debian 12, standard persistent disk **≤ 30 GB**.
3. Create it, then SSH in (the "SSH" button in the console works fine).

> You do **not** need to open any firewall ports. All traffic comes in through
> Tailscale, not the public internet.

## 2. Install Tailscale on the VM

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Open the printed URL to authorize the VM into your tailnet. Then give it a clean
name so the URL is memorable:

```bash
sudo tailscale set --hostname moro
```

In the **Tailscale admin console → DNS**, make sure **MagicDNS** and
**HTTPS Certificates** are both enabled (required for the `.ts.net` HTTPS cert).

## 3. Drop in the server

Copy `server.py` from this folder onto the VM (e.g. into `~/`). Quick test:

```bash
python3 server.py        # should print "MoroTracker store on 127.0.0.1:8787 ..."
```

Ctrl-C once you see it start.

## 4. Expose it over HTTPS on the tailnet

```bash
sudo tailscale serve --bg 8787
```

This serves `https://moro.<your-tailnet>.ts.net/` and proxies to the local
server. Find your exact URL with:

```bash
tailscale serve status      # shows the https://moro.<tailnet>.ts.net mapping
```

Test from another device that's on your tailnet:

```
https://moro.<your-tailnet>.ts.net/state   -> should return  {}
```

## 5. Keep it always running (systemd)

So the store restarts on reboot/crash. Create `/etc/systemd/system/moro.service`:

```ini
[Unit]
Description=MoroTracker state store
After=network.target

[Service]
ExecStart=/usr/bin/python3 %h/server.py
Restart=always
# Optional overrides:
# Environment=MORO_DATA=%h/moro-state.json
# Environment=MORO_ORIGIN=https://rfc1928.github.io

[Install]
WantedBy=default.target
```

If you put `server.py` in your home dir and run as your user:

```bash
sudo loginctl enable-linger $USER          # let the user service run without login
systemctl --user daemon-reload             # (or use the system unit above with sudo)
sudo systemctl daemon-reload
sudo systemctl enable --now moro
sudo systemctl status moro                 # confirm it's active
```

`tailscale serve --bg` persists across reboots on its own.

## 6. Point the app at it

In `index.html`, set the endpoint near the top of the `<script>` storage block:

```js
const SYNC_ENDPOINT = 'https://moro.your-tailnet.ts.net';   // no trailing slash, no /state
```

Commit & push to `main`. Done. The app now:

- saves to localStorage instantly (always),
- pushes changes to the VM ~0.8 s later when your tailnet is reachable,
- on load, pulls the VM copy and **merges** it with local.

---

## Notes & gotchas

- **Every device must run Tailscale** (logged into your tailnet, MagicDNS on) to
  sync. Without it, `moro.<tailnet>.ts.net` doesn't resolve/route and the app
  silently uses localStorage only — that's the intended fallback.
- **Merge is additive**: completions are unioned across devices, so you never
  lose a checkmark. The flip side — **un-checking an exercise won't reliably
  propagate** if another device still has it checked (the union re-adds it). For
  a habit tracker that's the safe trade-off.
- **Backup**: the whole dataset is one file. `cat ~/moro-state.json` (or scp it
  off the VM) is a complete backup. You can also paste it into a new VM's file
  to migrate.
- **Security**: the server binds to `127.0.0.1` and is only published via
  Tailscale Serve, so it's never on the public internet. CORS is locked to your
  GitHub Pages origin.
