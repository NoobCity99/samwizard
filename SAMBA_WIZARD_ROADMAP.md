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

## Suggested Milestones

### Milestone 1: Clickable Mock Wizard

Build the complete wizard UI with mock data and no real system changes.

Pages:

```text
Welcome
System Check
Drive Selection
Share Name
User Setup
Review
Apply
Done
```

Goal:

```text
The user can click through the full setup flow.
```

---

### Milestone 2: Real System Detection

Replace mock data with real read-only system information.

Detect:

```text
Hostname
Local IP address
Ubuntu version
Samba installed/not installed
Available drives/partitions
Mounted folders
```

Goal:

```text
The wizard can accurately describe the server without changing it.
```

---

### Milestone 3: Samba Install Test

Add controlled Samba installation.

Actions:

```text
apt update
apt install samba
verify smbd service
```

Goal:

```text
The wizard can install Samba and confirm it is available.
```

---

### Milestone 4: Simple Folder Share

Before dealing with external drives, create a basic Samba share from a known folder.

Example:

```text
/srv/samba/testshare
```

Goal:

```text
Windows can connect to a wizard-created Samba share.
```

---

### Milestone 5: Drive-Based Share

Add drive/partition selection and persistent mounting using UUIDs.

Goal:

```text
The wizard can create a Samba share on a selected existing drive or partition.
```

No formatting yet.

---

### Milestone 6: Installer Script

Create the bootstrap installer that installs dependencies, copies the app, starts the service, and prints the wizard URL.

Goal:

```text
A novice can start the wizard with one command.
```

---

## Future Expansion Ideas

Later versions may add:

```text
Multiple shares
Multiple users
Guest shares
Drive formatting with heavy warnings
NTFS/exFAT support improvements
Backup job setup
Robocopy helper generation for Windows
Tailscale-aware connection instructions
Cockpit plugin version
Server dashboard
One-time setup code
Wizard self-disable after completion
```

These should not distract from the MVP.

---

## North Star

The project succeeds when a beginner can go from a fresh Ubuntu Server install to a working private Windows-accessible network share without needing to understand Samba, Linux mounts, config files, or command-line administration.

```text
One command → browser wizard → working Samba share
```
