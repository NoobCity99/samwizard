#PHASE 2 PLAN

## STATUS OF PHASE 1 of SAMWIZARD APP
Currently The app successfully walks a novice user through the process of installing SAMBA and mounting a drive on their Ubuntu server; using a GUI interface they interact with on their PC.  ULtimately allowing them to create their own 'cloud drive' on their network. 

## Phase 2 will expand on that by adding the following features. 
    1: A landing page that introduces the user to SAMWIZARD, it's purpose and abilities. 
    2: Present the user with 3 paths to go down. 
        a: Installing Just SAMBA and setting up a share drive (currently exists)
        b: Installing SAMBA followed by Installing Tailscale , allowing them to access their share drive via encrypted tunnel from anywhere. 
        c: A fun & novice friendly tutorial, teaching the user about the basics of Ubuntu Server stucture & flow;   CLI Ubuntu commands , what they mean, how to install programs and update their server, etc. (this section will likely grow a lot over time.)
    3: Enabling ufw for both SAMBA & Tailscale is probably advised, so you will need to determine where best in the new flows (and perhapas existing SAMBA set-up flow) the ufw step should be inserted. 

### MY ASSUMPTIONS: Advise me if I'm incorrect
    1: The modular structure of the APP would mean Adding install wizard flows for other programs poses little risk to existing flows as they are like seperate roadways forking off of the same starting point or at the end of another. 
    

## Steps to bulid out Phase 2

### Step 1: COMPLETED (SEE BELOW) 
 
### Step 2: Add Tailscale as Part 2 of the Samba Setup

#### Goal

Build a Tailscale setup path that acts as "Part 2" after the user has already created a Samba share, and is WHOLLY SEPERATE from any functional backend coding of current SAMBA Install Wizard.... we don't want them intertwined. 

The purpose is not simply to install Tailscale. The purpose is to help the user access the same Samba share from their own devices through Tailscale when they are away from home.

The wizard should guide the user from their original local-only Samba address:

    \\LOCAL_SERVER_IP\SHARE_NAME

Example:

    \\192.168.1.50\Backups

To their new Tailscale-accessible Samba address:

    \\TAILSCALE_IP\SHARE_NAME

Example:

    \\100.101.102.103\Backups

For now, do not mention MagicDNS. The user already has two addresses to understand:

1. Local network IP address
2. Tailscale IP address

Keep the explanation focused on those two addresses only.

---

#### Core User Explanation

The wizard should clearly explain:

    Your Samba share is still the same shared folder.
    Tailscale does not replace Samba.
    Tailscale gives your own devices a private encrypted route back to this server.

Simple explanation:

    At home, your Windows PC reaches the share through your home network address.
    Away from home, your Windows PC reaches the same share through your Tailscale address.

Show this comparison clearly:

    At home:
    \\192.168.1.50\Backups

    Away from home using Tailscale:
    \\100.101.102.103\Backups

Important user-facing line:

    The folder did not move. The share did not change. Only the address used to reach it changed.

---

#### Scope Boundary

For Step 2, do NOT implement or explain:

- MagicDNS
- Tailscale Serve
- Tailscale Funnel
- Exit nodes
- Subnet routers
- Tailnet ACL editing
- HTTPS setup
- Public internet sharing
- Advanced Tailscale admin settings

This path should only connect the existing Samba share to the user's private Tailscale network.

---

#### Recommended Page Flow

##### Page 1: Continue Your Samba Setup

This page should appear after the normal Samba setup is complete, or from the landing page if a Samba share already exists.

Purpose:

- Remind the user what they already created.
- Show their current local Samba path.
- Explain that Tailscale adds private remote access to the same share.

Example text:

    Your Samba share is working on your home network.

    Current local address:
    \\192.168.1.50\Backups

    Next, SamWizard can help connect this server to Tailscale so your own devices can reach this same share when you are away from home.

Button:

    Set Up Tailscale Access

---

##### Page 2: What Tailscale Changes

Explain the before/after.

Before Tailscale:

    Your Windows PC must be on the same home network as the server.

After Tailscale:

    Your Windows PC can reach the server through your private Tailscale network.

Suggested visual:

    Before:

    Windows PC
       |
    Home Router
       |
    Ubuntu Server
       |
    Samba Share

    After:

    Windows PC with Tailscale
       |
    Private Tailscale Tunnel
       |
    Ubuntu Server with Tailscale
       |
    Same Samba Share

Important wording:

    Tailscale does not make your Samba share public.
    It only lets devices signed into your Tailscale account reach it.

---

##### Page 3: Tailscale System Check

Check and display:

- Is Samba configured?
- What is the current Samba share name?
- What is the current local Samba path?
- Is Tailscale installed?
- Is the Tailscale service running?
- Is the server logged into Tailscale?
- Does the server have a Tailscale IP address?

Display example:

    Samba share: Backups
    Local address: \\192.168.1.50\Backups
    Tailscale: Not installed
    Tailscale address: Not ready yet

If no Samba share exists, do not continue directly into Tailscale. Show:

    SamWizard needs a Samba share first so it can show you what address to use after Tailscale is connected.

Then link back to the Samba setup path.

Possible backend checks:

    command -v tailscale
    systemctl is-active tailscaled
    tailscale status --json
    tailscale ip -4

---

##### Page 4: Install Tailscale

FIRST : Prompt user with clickable link to goto : https://tailscale.com/download  , download for their OS and install/login. 
Explain this will set their windows machine up as the first authorized computer on their Tailnet. 

Once they confirm (add button) they've created and account, downloaded tailscale , added their first PC... then...

Proceed with step two: 
If Tailscale is not installed, install it on the Ubuntu server.

Describe this to the user as:

    Installing private remote access support...

Avoid overly technical wording such as:

    Installing VPN daemon...

After install, verify:

    command -v tailscale
    systemctl is-active tailscaled

If install fails, show a novice-readable error and suggest checking internet access.

-

---

##### Page 5: Sign In / Authorize This Server

Start the Tailscale connection process and show the login URL returned by Tailscale.

User-facing explanation:

    Tailscale needs you to approve this server in your Tailscale account.

    Open the link below, sign in, and approve this server.

After approval, the user clicks:

    I approved the server. Check again.

Then the wizard verifies that a Tailscale IP exists.

Success condition:

- Tailscale is running.
- The server is connected.
- A Tailscale IPv4 address is available.

---

##### Page 6: Your New Samba Address

This is the most important page.

Show the before/after clearly.

Example:

    Your Samba share is still:
    Backups

    At home, use:
    \\192.168.1.50\Backups

    Away from home with Tailscale, use:
    \\100.101.102.103\Backups

Add this note:

    The folder did not move.
    The share did not change.
    Only the route to reach it changed.

This page is the success state of the Tailscale path. Do not end the flow with only "Tailscale is installed." End the flow by showing the new Samba address the user should use.

---

##### Page 7: Set Up Your Windows PC

Explain that the remote Windows PC also needs Tailscale.

User-facing instructions:

    To use this from your Windows PC:

    1. Install Tailscale for Windows.
    2. Sign into the same Tailscale account.
    3. Make sure Tailscale says Connected.
    4. Open File Explorer.
    5. Enter the Tailscale Samba address:

       \\100.101.102.103\Backups

---

#### Address Priority

When showing connection options, use this order:

1. Local home network Samba path
2. Tailscale Samba path

Example:

    Home network address:
    \\192.168.1.50\Backups

    Tailscale address:
    \\100.101.102.103\Backups

Do not show MagicDNS in this step.

---

#### UFW / Firewall Note

Because this path connects Samba access with Tailscale access, firewall handling must be careful.

For Step 2, do not automatically enable UFW unless the existing app already has a tested firewall workflow.

Instead:

- determine where best to insert a "ACTIVATE FIREWALL" button with an explanation of what it means to them. 

 firewall logic may need to distinguish between:

    Allow Samba on local LAN
    Allow Samba on tailscale0
    Do not expose Samba publicly

But all those details can be handled in the back end, the user should get a clear understanding that "your data is safe and accessible only by you"


Key beginner message:

    Firewall settings should protect the server without blocking the private Samba connection you just created.

---

#### Backend Implementation Notes

Create Tailscale-specific backend helpers instead of mixing commands into the Samba flow.

Suggested structure:

    app/
      routes/
        tailscale.py
      services/
        tailscale_manager.py
        firewall_manager.py

Suggested Tailscale manager functions:

    is_tailscale_installed()
    is_tailscale_service_running()
    get_tailscale_status()
    get_tailscale_ipv4()
    install_tailscale()
    start_tailscale_login()

Avoid arbitrary command execution from the browser. The UI should call named backend actions only.

---

#### Success Criteria

Step 2 is complete when:

- A user can finish Samba setup and then continue into Tailscale setup.
- A user can also reach the Tailscale path from the landing page if a Samba share already exists.
- The wizard refuses to continue if no Samba share exists yet.
- The wizard detects whether Tailscale is already installed.
- The wizard installs Tailscale if missing.
- The wizard starts the Tailscale authentication process.
- The user is shown the Tailscale login URL.
- After login, the wizard confirms the server has a Tailscale IP.
- The final page shows the same Samba share using both addresses:
  - local LAN IP path
  - Tailscale IP path
- Existing Samba setup still works unchanged.
- If Tailscale setup fails, the user sees a clear explanation instead of a raw terminal dump.

---

#### Testing Checklist

Test these cases:

1. Fresh Ubuntu Server with Samba share configured and no Tailscale installed.
2. Tailscale installed but not connected.
3. Tailscale installed and already connected.
4. No Samba share exists yet.
5. No internet connection.
6. UFW inactive.
7. UFW active.
8. User does not complete Tailscale browser login.
9. Re-running the Tailscale wizard after successful setup.
10. Windows connection using the local IP path.
11. Windows connection using the Tailscale IP path.

---

#### Core Instruction for Codex

Do not treat Tailscale as a separate destination. (although landing page can have a tiny link in the footer if user needs to go straight here because they only did SAMBA previously)

Code This process so it's functional backend is not intertwined with the SAMBA SET-UP Wizard in such a way, that if the Tailscale wizard was ever removed, it would effect the samba wizard. 

The Tailscale path is a continuation of the Samba setup.

The final output of this path must not simply say:

    Tailscale is installed.

The final output must say:

    Here is the new address to use for your Samba share through Tailscale.

The user should leave this flow understanding that:

- Samba is still the file-sharing system.
- Tailscale is the private road back to the server.
- The share name stays the same.
- The IP address before the share name changes.


## COMPLETED STEPS & SUMMARIES
AFter each STEP is completed, move it to this section and include short summary of what actions were taken. 

### Step 1: RESULTS
   1: Create an html landing page based on layout & design decribed by me. I will provide a basic layout example. Lay out will detail where text and images will roughly need to be on the landing page.  Provide me with instructions on where to save the image files, what to name them, where to make minor adjustments (sizing , padding, etc). 
   2: Landing page will have buttons for the user to choose their path, only the SAMBA path button should be live and linked to current SamWizard flow... the two NEW paths are not built yet, so their buttons should NOT be linked to anything. 

   Changes made:
Added / as the new landing page in [app/main.py (line 278)](/mnt/c/Users/mstre/Python_Files/SAMWIZARD/app/main.py:278).
Moved the existing Samba wizard welcome screen to /samba in [app/main.py (line 289)](/mnt/c/Users/mstre/Python_Files/SAMWIZARD/app/main.py:289).
Added the new landing template at [landing.html (line 1)](/mnt/c/Users/mstre/Python_Files/SAMWIZARD/app/templates/landing.html:1).
Added landing layout/styles in [styles.css (line 1103)](/mnt/c/Users/mstre/Python_Files/SAMWIZARD/app/static/styles.css:1103).
Added route tests for landing behavior, disabled placeholder paths, /samba, and /start in [test_system_check_routes.py (line 175)](/mnt/c/Users/mstre/Python_Files/SAMWIZARD/tests/test_system_check_routes.py:175).
Made an existing async apply-flow test deterministic so the suite does not fail based on background-job timing.

## GOAL: A rich tool for new Linux/Ubuntu Server Users

