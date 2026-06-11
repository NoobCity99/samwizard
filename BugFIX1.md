# BUG FIX DOCUMENT
This will serve as a living document of updates , fixes & changes after first deployment.  Progress will be archived here for you to reference and understand where we are at in the process.

First deployment went very well. Dependancies and such were installed clean and the web interface & log looked good.

## SAMBA_WIZARD_ROADMAP.MD as reference material
Consider the roadmap as a historical document with reference material of how we got here. Future updates may conflict with some of it's content,  ask if anything appears dangerously out of scope.

## BUGS needing attention
Move resolved BUGS to the '## Resolved Bugs' section below as you resolve them.

## CHANGES to APP
Move completed changes to the '## Completed Changes' section below after changes have been coded.

### CHANGE 3: ufw enabling for tailscale.

 Future updates to app will include installing TAILSCALE to allow users to access their samba share drives remotely. I understand it's advisable to have ufw enabled and have samba and/or tailscale authorized to pass.  Devise a plan to include a new step in the process to activate ufw with the user.  If having tailscale installed first is a safer order of operations.... plan the best implimentation with these factors in mind.

# RESOLVED ITEMS
Here will be the historical record of changes and fixes, they'll include the original issue AS WELL AS a summary of what CODEX did to resolve it.

## Resolved Bugs

### BUG 4: Stale language about milestones
Original issue:
    - Some pages still had old milestone/mock-era warning language, including sudo-until-launcher text.
    - The app is now in real-world testing, so stale training-wheel language needed to be removed.

Resolution:
    - Removed the obsolete Apply page notice about needing sudo until an installer milestone.
    - Reworded System Check to explain that Windows, WSL, or non-Ubuntu may report limited details, and that real setup testing should use Ubuntu Server.
    - Updated README milestone-era language to current release and real setup wording.
    - Removed stale mock-log CSS naming and refreshed the development session secret fallback string.
    - Kept root-required backend failure messages because they still protect real system changes when the app is launched without sudo.

### BUG 1: DRIVE MOUNTING Error
Original issue:
    1. SamWizard detected /dev/sda1 with its original NTFS UUID.
    2. Mount failed because the old Windows NTFS filesystem was unsafe.
    3. The drive was manually formatted.
    4. The user clicked BACK in the wizard and retried the same visible device, /dev/sda1.
    5. Formatting changed the filesystem UUID.
    6. SamWizard reused the old cached UUID and wrote it to /etc/fstab.
    7. Later mount failed with: can't find UUID=8A5591736A17E820.

Resolution:
    - Apply now refreshes the selected drive by stable device path immediately before writing /etc/fstab.
    - The current UUID and filesystem are read from lsblk, with blkid as a fallback.
    - Stale Samba Wizard fstab blocks for the same mount path are removed before writing the refreshed entry.
    - Apply runs systemctl daemon-reload, mounts the selected mount point, and verifies it with findmnt before continuing.
    - Unit tests cover the same device path with a changed UUID, stale fstab cleanup, daemon-reload/mount/findmnt order, and findmnt failure handling.

### BUG 2: READ / WRITE Permissions
Original issue:
    1. During the first test, the drive that was eventually mounted appeared to be read-only.
    2. SamWizard needed a clear read/write versus read-only choice for external drives.
    3. Existing NTFS external HDDs from Windows, plus common Mac-friendly formats, needed better handling.

Resolution:
    - Drive Selection now defaults external drives to read/write and also offers read-only.
    - External drive shares now point at the whole mounted drive root so existing files are available.
    - Apply writes filesystem-aware fstab entries for Linux filesystems, NTFS, exFAT/FAT, and conservative read-only HFS/HFS+.
    - APFS is blocked as unsupported because Linux write support remains experimental.
    - Apply verifies the final mount options with findmnt and fails if read/write was requested but Linux mounted the drive read-only.
    - Read/write drive setup runs a private-user write/delete probe before Samba is configured.
    - Read-only drive setup skips ownership, chmod, folder creation, and write probes, and writes Samba as read only.
    - samwizard.sh installs NTFS and exFAT support, with HFS tools as best-effort optional packages.
    - Unit tests cover mount option generation, route storage/display, read-only Samba config, read-only skip behavior, read-only mount failure, and write-probe failure.

### BUG 3: Mount Successful, but Browser Hangs
Original issue:
    1. Samba setup appeared to work on the real server.
    2. The selected drive mounted successfully.
    3. Windows could access the share via IP and Samba username/password.
    4. The browser hung after clicking Apply and did not visibly reach the confirmation page.
    5. The extracted backend log showed Apply reached `systemctl restart smbd` and that command completed.

Resolution:
    - Apply now starts a background job and immediately redirects the browser to a live progress page.
    - The progress page shows an indeterminate spinner/progress bar, latest Apply command, stale-command waiting message, and full-log link.
    - Apply subprocesses now have command-specific timeouts and return friendly timeout failures instead of hanging indefinitely.
    - Apply command logging now records both "Starting command..." and the final completion/failure/timeout result.
    - Successful Apply completion is reconciled through `/apply/status`, then redirects to `/done` without rerunning full system detection.
    - Failed Apply jobs send the browser back to Apply with the failed step displayed.
    - Unit tests cover progress redirects, status polling, timeout conversion, unexpected Apply errors, password masking, and Done rendering from cached system details.



## Completed Changes

### CHANGE 1: Future Mounting of Drives in SAMBA
Original change:
    - If Samba is already installed, SamWizard should inspect the existing Samba setup and confirm whether a Samba user exists.
    - If exactly one Samba user exists, the wizard should switch to an add-drive flow: choose drive, name share, review, apply.
    - The add-drive flow should reuse the existing Samba user instead of creating a new user.
    - The Samba card should offer a "See your Samba System" page with novice-friendly status.
    - If Samba is installed but no users exist, the wizard should continue through first-time setup.

Resolution:
    - Samba detection now checks configured users with pdbedit, configured shares with testparm, active sessions with smbstatus, and service status with systemctl.
    - System Check stores a setup mode: first-time setup, add-drive mode for exactly one existing Samba user, or a stop state for multiple Samba users.
    - Add-drive mode skips User Setup, shows the reused Samba user on Review, and applies without asking for or changing the Samba password.
    - Apply can now verify an existing Samba user instead of creating one, then continues through drive mount, Samba share config, validation, and reload.
    - The Samba card now links to a read-only "See your Samba System" page with plain-language users, shares, active connections, and service details.
    - Unit tests cover Samba detection, mode routing, passwordless add-drive Apply, skipped user creation, and the Samba summary page.

### Change .5: Remove shared folder option
Removed the user-facing server-folder option from Drive Selection in share_targets.py (line 22).
Added lsblk parent disk tracking in system_info.py (line 444).
Excludes partitions mounted at /, /boot, or /boot/efi, plus sibling partitions on the same OS disk, with diagnostics showing part of the server OS drive.
Updated Drive Selection copy and empty state in drive_selection.html (line 7): no eligible drive now stops the user and tells them to connect a drive.
Stale server_folder sessions now redirect back to Drive Selection via main.py (line 66).
Direct backend calls with non-drive locations now fail with drive_required in system_actions.py (line 108).
Updated README wording for the external/additional-drive-only flow.


### CHANGE 2: Can we rename install.sh ?

The command to run SAMWIZARD in linux is 'sudo bash install.sh' , if I'm not mistaken.  I'd love for the user to be able to type in 'sudo bash samwizard' or something clearly indicating "we're about to run SAMWIZARD" ... the name 'install.sh' feels wildly generic for a novice user to remember in the future as the specific command for SAMWIZARD. Could we change it to SamWizard.sh , ex: user runs 'sudo bash samwizard.sh' ? 

Resolution:
    - The root installer script was renamed from install.sh to samwizard.sh.
    - The installer now tells non-root users to rerun with `sudo bash samwizard.sh`.
    - README release and install instructions now use `samwizard.sh` as the branded release asset and command.
    - Installer tests now validate `samwizard.sh` directly.
    - No install.sh compatibility wrapper is kept; the next release should upload samwizard.sh.

### CHANGE 4: Small Changes
Original change:
    - Add a clickable copy icon on the Done page Windows Path card.
    - Change the top-left app text from "SAMBA WIZARD" to "SamWizard".
    - Add an assets folder for future icons and images.

Resolution:
    - Done now includes an accessible copy button for the Windows path with clipboard support and a fallback copy path.
    - Visible app branding, browser titles, and the log page now use "SamWizard".
    - Added `app/static/assets/` as the served asset folder for future icons/images.
    - The current three colored dots remain until the final logo is ready.
    - Logo guidance: use transparent SVG when possible; transparent PNG or WebP is also fine. Provide a square source at 128x128 or larger. The header display target should be roughly 28-36 px tall.
