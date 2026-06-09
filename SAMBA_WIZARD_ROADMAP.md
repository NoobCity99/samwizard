# Samba Wizard Project Roadmap

## Project Goal

Build a simple, novice-friendly web-based setup wizard for Ubuntu Server that helps users create a private Samba file share without needing to understand Linux commands, Samba configuration, drive mounting, or terminal workflows.

The intended user is a complete beginner who can install Ubuntu Server and paste one command, but should not need to manually run `apt`, edit config files, understand `/etc/fstab`, or write Samba share definitions.

---

## Core Product Concept

The wizard should run directly on the Ubuntu Server and be accessed from another computer through a browser.

Target user flow:

```text
1. User installs Ubuntu Server
2. User runs one bootstrap install command
3. The wizard starts on the server
4. User opens a local web page from their main PC
5. Wizard walks them through Samba setup
6. User receives a Windows share path like \\192.168.1.50\Backups
```

The Windows PC should only need a browser. The actual Samba installation, drive detection, mounting, and configuration should happen on the Ubuntu Server.

---

## MVP Scope

The first version should focus on one successful use case:

> Create one private Samba share on one existing drive or folder.

### Include

- Local web UI
- System check page
- Drive/folder selection
- Share name entry
- Samba username/password creation
- Review screen before applying changes
- Samba installation
- Basic share creation
- Windows connection instructions

### Exclude for Now

- Drive formatting
- RAID/ZFS/LVM
- Multiple users
- Guest/public shares
- Advanced permissions
- Tailscale integration
- Cockpit integration
- Backup automation
- Dashboard features
- Internet-facing access
- Complex networking features

---

## Technical Direction

Preferred stack:

```text
Backend: Python + FastAPI
Frontend: Jinja2 templates + plain HTML/CSS
Runtime: Ubuntu Server
Service management: systemd eventually
State storage: simple JSON file for early versions
```

Avoid unnecessary complexity in the MVP. No database, no React/Vue/Svelte, and no advanced plugin architecture unless clearly needed later.

---

## Design Principles

### 1. Novice-first language

The interface should avoid exposing Linux implementation details unless necessary.

Prefer:

```text
Installing Windows file sharing support...
```

Instead of:

```text
Running sudo apt install samba...
```

Prefer:

```text
Choose the drive you want to share
```

Instead of:

```text
Select block device /dev/sdb1
```

Advanced details can exist later, but should not be the default experience.

---

### 2. Safe by default

The MVP should not erase, format, repartition, or destructively modify drives.

Before modifying system files, the app should eventually make backups of:

```text
/etc/samba/smb.conf
/etc/fstab
```

Config changes should be validated before services are restarted.

---

### 3. One working path first

Do not try to support every Samba scenario immediately.

The first success target is:

```text
Ubuntu Server + one drive/folder + one private Samba user + one share
```

Once that works reliably, expand.

---

### 4. Browser-based setup

The wizard should be controlled through a local web page served by the Ubuntu Server.

Example final output from installer:

```text
Samba Wizard is ready.

Open this from your main computer:
http://192.168.1.50:8080
```

---

### Milestone 5.2: Redesign how log appears

    The command log feature should be accessable by an icon at the top right of the window. (not at the bottom of the checks page) When user clicks on icon (use a paper & pen icon or something similar) a new tab opens, ex: xxx.x.x.x:8080/logs , it should show live view of all commands and they can reference it throughout the process. 

    ALSO: investigate the drive selection feature, it's not showing me available drives just saying it will create a folder , if that's just because im on my local wsl,  I'll just wait until i test this out on a live server to give more notes on that topic. 

### Milestone 6: Bootstrap Installer and GitHub Release Asset

Create a novice-friendly bootstrap installer for Ubuntu Server.
Installer Responsibilities:
1. Confirm the system is Ubuntu Server or compatible Ubuntu.
2. Check for required commands: curl, python3, python3-venv, pip, systemctl.
3. Install missing dependencies using apt.
4. Create the application directory:
   /opt/samwizard/
5. Download the versioned SamWizard app bundle from GitHub Releases.
6. Extract/copy the app into /opt/samwizard/.
7. Create a Python virtual environment:
   /opt/samwizard/venv/
8. Install Python requirements.
9. Create a systemd service named:
   samwizard
10. Start the samwizard service.
11. Enable the service to start on reboot, unless intentionally skipped.
12. Detect the server's local IP address.
13. Print the browser URL for the user, for example:
   http://192.168.1.50:8080
14. Provide clear error messages if installation fails.
The primary release asset should be:

```text
install.sh
```


### North Star

The project succeeds when a beginner can go from a fresh Ubuntu Server install to a working private Windows-accessible network share without needing to understand Samba, Linux mounts, config files, or command-line administration.

```text
One command → browser wizard → working Samba share
```
