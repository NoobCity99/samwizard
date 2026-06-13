# SamWizard

SamWizard is a local FastAPI setup wizard for creating one private Samba share
from Ubuntu Server.

The app uses FastAPI, Jinja2 templates, and plain CSS. The System Check page can
read Linux system details such as hostname, local IP addresses, `/etc/os-release`,
Samba command/package evidence, `lsblk` JSON, `findmnt` JSON, and `/proc/mounts`
as a fallback.

The System Check page is read-only. The Apply step can make real system changes
when the app is started with sudo: install Samba, mount a selected external or
additional drive by UUID, update Samba config, and restart Samba.

## Run locally for read-only screens

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```

Open:

```text
http://127.0.0.1:8080
```

## Wizard flow

The clickable flow includes:

```text
Welcome -> System Check -> Drive Selection -> Share Name -> User Setup -> Review -> Apply -> Done
```

The System Check page shows real detected data when the host operating system
provides it, including a read-only internet connectivity check. If internet is
missing, the page lets you recheck after connecting ethernet or connect Wi-Fi
with a managed Netplan file when the app is running with sudo.

The Apply step performs real setup only when the app is running with root access.
For local WSL testing before using the installer, start the app with:

```bash
sudo .venv-wsl/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

The top-right log icon opens `/logs` in a new tab. It shows commands and
responses from the current browser session. Passwords and secret input are
hidden as `********`, and the log can be cleared from the UI. Logs are
session-only and disappear when the app process restarts.

## SamWizard Academy

The landing page links to `/academy`, a beginner-friendly Ubuntu Server and
command-line learning map. Academy progress is stored as JSON in:

```text
${SAMWIZARD_STATE_DIR}/academy-progress.json
```

The installer sets `SAMWIZARD_STATE_DIR=/var/lib/samwizard`. Local development
uses `.samwizard-state` unless the environment variable is overridden. Academy
lessons live in `app/academy/trees/ubuntu_cli_basics.json`, so lesson text,
unlock links, and hex map positions can be edited without changing route code.

## Update the logo

The header logo is served from:

```text
app/static/assets/samwizard_logo.png
```

To change it, replace that file with another PNG using the same filename, then
refresh the browser. A square transparent PNG is easiest to manage; `128x128`
or larger is recommended. The current source image is `1254x1254`.

SVG also works. Add the SVG to `app/static/assets/`, then update the logo `src`
in `app/templates/base.html` from `/assets/samwizard_logo.png` to the SVG file.

To adjust the displayed size, edit `.app-logo` in `app/static/styles.css`.
Change `width` and `height` together to keep the logo square. The current
display size is `42px` by `42px`. The `<img>` also has matching `width` and
`height` attributes as a fallback if the stylesheet is cached or slow to load.
CSS still controls the final rendered size when loaded.

## Build release assets

From WSL or Linux:

```bash
if [ -x .venv-wsl/bin/python ]; then PY=.venv-wsl/bin/python; else PY=python3; fi
$PY build_release.py --version 0.7.0 --output dist/samwizard-app.tar.gz
```

Upload these files to the GitHub Release:

```text
samwizard.sh
dist/samwizard-app.tar.gz
```

The installer expects the release bundle at:

```text
https://github.com/NoobCity99/samwizard/releases/latest/download/samwizard-app.tar.gz
```

For pre-release testing, override the bundle URL:

```bash
sudo SAMWIZARD_APP_URL="https://example.test/samwizard-app.tar.gz" bash samwizard.sh
```

## Install on Ubuntu Server

Use a real Ubuntu Server system with systemd. WSL is useful for unit tests, but
it is not the target for the service installer.

```bash
curl -fsSL https://github.com/NoobCity99/samwizard/releases/latest/download/samwizard.sh -o samwizard.sh
sudo bash samwizard.sh
```

The installer will:

```text
Install required Ubuntu packages
Install SamWizard into /opt/samwizard
Create /opt/samwizard/venv
Write /etc/samwizard/samwizard.env
Create and start samwizard.service
Print the local browser URL
```

Useful service commands:

```bash
sudo systemctl status samwizard
sudo systemctl restart samwizard
sudo journalctl -u samwizard --no-pager -n 100
```

If UFW is active and the page does not open from Windows, allow the wizard port:

```bash
sudo ufw allow 8080/tcp
```

## First real-world test

Use a real Ubuntu Server machine or VM with systemd. Attach one known-safe
existing drive or partition that already has a filesystem and UUID. The wizard
does not format, erase, or repartition drives.

1. Install SamWizard with the release `samwizard.sh`.

2. Open the printed URL from the Windows laptop. Also open the live log page:

   ```text
   http://SERVER-IP:8080/logs
   ```

3. Test the internet path. If Wi-Fi behavior needs validation, start without
   ethernet and use the Wi-Fi form on System Check. Confirm the log shows the
   managed Netplan file step, `netplan generate`, `netplan apply`, and the
   internet recheck. If ethernet is connected instead, click **OK, I connected
   ethernet** and confirm the check passes.

4. On Drive Selection, choose the real eligible external or additional drive
   partition. Eligible means Linux reports it as a partition with a filesystem
   and UUID, and it is not part of the server's operating system drive.

5. Complete Share Name, User Setup, Review, and Apply. Apply should install or
   verify Samba, write a UUID-based `/etc/fstab` entry, mount under
   `/srv/samba/drives/`, share the mounted drive root, update Samba config,
   validate with `testparm`, and restart or reload Samba.

6. On Done, copy the Windows path, for example:

   ```text
   \\192.168.1.50\Backups
   ```

7. Connect from Windows File Explorer using the Samba username and password.
   Copy a small test file into the share and confirm it appears on the Linux
   mounted path.

8. Reboot the server. Confirm `samwizard.service` starts again, the drive
   remounts, and the Windows share still works.

## Run unit tests

From Windows PowerShell in VS Code:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest discover -s tests
```

These tests use mocked command output, so they can run on Windows without
requiring Linux tools such as `lsblk` or `findmnt`.

From WSL, prefer the repo-local WSL virtual environment:

```bash
if [ -x .venv-wsl/bin/python ]; then .venv-wsl/bin/python -m unittest discover -s tests; else python3 -m unittest discover -s tests; fi
```

## Test in WSL2 Ubuntu

Use these steps on this Windows laptop when you want to see the real Linux
detection results.

1. Open Ubuntu from the Windows Start menu, or open a VS Code terminal connected
   to your WSL Ubuntu environment.

2. Go to this project through the `/mnt/c` Windows drive path:

   ```bash
   cd /mnt/c/Users/mstre/Python_Files/SAMWIZARD
   ```

3. Create a WSL-specific virtual environment. This avoids mixing Windows Python
   files with Linux Python files:

   ```bash
   python3 -m venv .venv-wsl
   source .venv-wsl/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Run the unit tests inside WSL:

   ```bash
   python -m unittest discover -s tests
   ```

5. Start the web app inside WSL:

   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
   ```

6. On Windows, open this address in your browser:

   ```text
   http://127.0.0.1:8080
   ```

7. Click through to **System Check**. You should see real values from the WSL
   Ubuntu environment, including the WSL hostname, local IP address, Linux
   version, Samba detection result, drives/partitions, and mounted folders.

8. If port `8080` is already busy, stop the other app or use a different port:

   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8081
   ```

   Then open:

   ```text
   http://127.0.0.1:8081
   ```

Useful read-only commands for comparing what the app shows:

```bash
hostname
hostname -I
cat /etc/os-release
if command -v smbd >/dev/null 2>&1; then smbd --version; else echo "smbd was not found"; fi
lsblk --json
findmnt --json
```

For real setup testing, stop the read-only server and restart with sudo using
the command above. Test Wi-Fi changes only on a server/network where applying
Netplan is acceptable. Test drive sharing only with a known safe existing
partition. The wizard does not format drives.
