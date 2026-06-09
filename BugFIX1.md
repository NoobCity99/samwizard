# BUG FIX DOCUMENT
This will serve as a living document of updates , fixes & changes after first deployment.  Progress will be archived here for you to reference and understand where we are at in the process.  

First deployment went very well. Dependancies and such were installed clean and the web interface & log looked good. 

## SAMBA_WIZARD_ROADMAP.MD as reference material 
Consider the roadmap as a historical document with reference material of how we got here. Future updates may conflict with some of it's content,  ask if anything appears dangerously out of scope. 

## BUGS needing attention
Move resolved BUGS to the '## Resolved Bugs' section below as you resolve them. 


### BUG 1: DRIVE MOUNTING Error 
1: Real-server test revealed a stale UUID bug caused by back-button flow after formatting.

Sequence:
    1. SamWizard detected /dev/sda1 with its original NTFS UUID.
    2. Mount failed because the old Windows NTFS filesystem was unsafe.
    3. The drive was manually formatted.
    4. The user clicked BACK in the wizard and retried the same visible device, /dev/sda1.
    5. Formatting changed the filesystem UUID.
    6. SamWizard appears to have reused the old cached UUID and wrote it to /etc/fstab.
    7. Later mount failed with: can't find UUID=8A5591736A17E820.

Needed fixes:
    1. Do not rely on cached UUID/device metadata when applying drive-based setup.
    2. Immediately before writing /etc/fstab, re-scan the selected partition with lsblk/blkid.
    3. Use the current UUID from the fresh scan.
    4. If the selected device path exists but its UUID changed since selection, show a warning or silently refresh it before apply.
    5. After writing /etc/fstab, run systemctl daemon-reload.
    6. Mount the specific mount point.
    7. Verify with findmnt before declaring setup successful.
    8. Add a test for “device path same, UUID changed between selection and apply.”

### BUG 2: READ / WRITE Permissions
    During the first test it appeard the drive that was enventually mounted was READ ONLY.   
    1: Confirm drives are mounted with READ / WRITE abilities...  OR Provide user with the ability to designate it READ or READ / WRITE. 
*NOTE* These users will often be mounting EXISTING NTFS external HDD they currently use on windows machine (or even a MAC), and want to be able to access remotely... so NTFS3 (or 3g) and MAC storage formats should be part of the install and samwizard should expect these kind of drives to be attached. 


## CHANGES to APP
Move completed changes to the '## Completed Changes' section below after changes have been coded. 

### CHANGE 1 : Future Mounting of Drives in SAMBA
If app detects SAMBA is already installed , it should run smbstatus in the background,  confirm if a samba user exists as well.  
  - IF YES: the user's path in the app changes from current flow of CHOOSE DRIVE -> NAME DRIVE -> NEW USER -> APPLY , to a new flow guiding them through adding a new drive to their samba share (ie: Mounting another external HDD they've decided to use) Similar flow but without creating a user. 
  - ALSO IF YES: A button should appear in the SAMBA Card on the System Check page that says "See your Samba System" Button will open a new tab displaying the outcome of a "Sudo smbstatus" command, but displaying in laymens terms so they understand what they're seeing. 
  - IF NO: And samba was installed but no users or shares set up... then user continues on as normal. 
  *NOTE* This app is meant for a first time novice to set up a samba share drive at home, so if they're looking to add new users and such, they're advanced enough to do it manually in ubuntu without the wizard, so no need to worry about new flow's that let them add new users.



# RESOLVED ITEMS
Here will be the historical record of changes and fixes, they'll include the original issue AS WELL AS a summary of what CODEX did to resolve it. 

## Resolved Bugs




## Completed Changes