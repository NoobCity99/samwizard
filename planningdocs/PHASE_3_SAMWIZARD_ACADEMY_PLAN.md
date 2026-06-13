# Phase 3 Plan: SamWizard Academy — Ubuntu Server & CLI Basics

## Goal

Build a new **SamWizard Academy** feature: a beginner-friendly tutorial system for learning Ubuntu Server and command-line basics through a video-game-style **hex skill tree**.

The Academy should feel like a guided learning map, not a documentation page.

Users should be able to open the Academy, click available skill tiles, read short lessons, complete simple exercises, mark skills complete, and unlock connected skills over time.

## Core Concept

The Academy screen should use a large hex-tile skill tree inspired by game upgrade menus.

At launch, only a few starter tiles are unlocked.

Most tiles should be visible but locked/grayed out.

When the user completes an unlocked skill, the next connected skill or skills should unlock.

Clicking a skill tile should open a long lesson card/panel on the left side of the screen.

The right side should remain the visual skill map.

It will need to be expandable for development, but will have an endgame & "Graduation" eventually. 

## Academy Topics

This tree will focus on:

**Ubuntu Server & CLI Basics** & **Understading your SAMBA Server & Tailscale**

Initial focus areas may include:

- What Ubuntu Server is
- What the terminal is
- Server identity: hostname, IP address, username
- Basic navigation
- Files and folders
- Drives and mounts
- Services
- Networking basics
- Permissions
- Reading command output and errors
- How Samba works
- How Tailscale works 

We'll need to know how you think lesson plans are formatting and input before I expand on a full tree

## Hard Rule: Academy Must Be Independent

Academy logic must be kept separate from the Samba and Tailscale modules.

Do not make Academy depend on Samba setup logic.

Do not import Samba or Tailscale services into Academy code.

The Academy may live inside the same FastAPI app for now, but it should be built as if it may later become a standalone application.

Shared visual assets, global styling, and landing-page integration are acceptable.

Backend learning logic, progress storage, lesson loading, skill unlocking, and API routes should be Academy-specific.

## Progress Storage

Academy must save user progress to a JSON file on the server.

The progress file should track at minimum:

- Which Academy tree is active
- Which skills are completed
- Which skills are unlocked
- Last opened skill if useful
- Version/timestamp metadata if useful

Use a durable server-side location suitable for app state.

Progress should survive browser refreshes, app restarts, and server reboots.

Progress saving should be safe against partial/corrupt writes where practical.

Do not require a database, this is to remain light-weight.

## Skill Tree Data

The tree should be data-driven.

Skill definitions should come from structured data, not hardcoded HTML.

Each skill should define:

- Stable skill ID
- Title
- Icon reference
- Short summary
- Lesson content
- Exercise instructions
- Unlock relationships
- Starting locked/unlocked state
- Optional map position/order data

Codex may choose the exact JSON shape.

The important requirement is that adding/editing skills later should not require rewriting core UI logic.

Plan for a scalable text format file that houses the data for each skill tile's data & content. Dev can add/edit/remove tiles. Each entry will need to identify where a new tile is to fall on the tree. Provide dev with options for how best to achieve this. 

## UI Behavior

The page should start with three clickable unlocked tiles.

Other linked tiles should be visible but locked.

Locked tiles should look disabled and should not be completable.

Clicking an unlocked or completed tile opens its lesson card.

The lesson card should occupy roughly one-third of desktop screen width.

The skill tree should occupy the remaining space.

The card should show the skill title, summary, lesson text, exercise, and completion control.

When the user clicks Complete, the backend should update progress and return the new tree state.

The frontend should then visually update completed and newly unlocked tiles.

## Visual Theme

Use a playful but readable “wizard academy / game skill tree” style.

see dir/planningdocs/batman.png for aesthetic inspiration. 

Preferred visual direction:

- Hexagonal skill tiles
- Dark server-console-style background
- Electric blue/cyan for unlocked skills
- Orange/gold for selected skills
- Green/blue glow for completed skills
- Gray/dim styling for locked skills
- Clear icon inside each hex
- Subtle connector lines between related skills if practical

Readability matters more than visual effects.

Avoid making the UI so decorative that lessons become hard to read.

## Icons

Use an existing icon library if it is sufficient.

Good enough is acceptable for the first version.

Allow icon references to be swapped later for custom SamWizard art, and provide me with parameters for custom icons. 

Do not block the feature waiting for final custom icons.
## Completion Rules

For the first version, completion can be manual.

The user reads the lesson, performs the exercise on their server, then clicks a **Complete** button.

Backend should verify that the skill was unlocked before allowing completion.

Completing a skill should unlock only the skills connected to it by the skill tree data.

Completed skills should remain clickable for review.

## Command Safety

Do not execute arbitrary user-entered commands from the web UI.

If command verification is added later, it must use predefined safe checks only.

Allowed future direction:

- A Button launches cmd prompt with 'ssh user@ip' entered, user puts in password. 
- Lesson instructs a specific command/check,  User pastes output for validation
- Backend checks simple expected text/patterns

Disallowed:

- Web UI terminal
- User types any command and backend runs it
- Academy becomes a general remote command executor

## Lesson Design

Short intro to topic with list of common commands;  their etymology and laymens explaination of purpose & outcomes. 

Instructions for a short exercise. 

Input block to paste results. 



## UX Rules

Locked tiles should still show a title or teaser when clicked/hovered if practical.

Locked tile messaging should explain what prerequisite skill unlocks it.

Users should always understand what to do next.

There should be a clear reset progress option, but it should require confirmation.

The Academy should not interfere with existing Samba or Tailscale setup workflows.

## Build Order

1. Create a static visual prototype of the Academy page.
2. Add hex tiles, locked/unlocked/completed states, and left-side skill card.
3. Move skill definitions into structured data.
4. Add backend route/API support for loading the tree.
5. Add server-side JSON progress persistence.
6. Add skill completion endpoint and unlock logic.
7. Add the first starter lessons for Ubuntu Server & CLI Basics.
8. Add polish: selected state, connectors, better icons, locked-skill explanations.

## Definition of Done for Phase 3 First Pass

The user can open SamWizard Academy from the landing page's "SamWizard Academy" button.

They see a hex skill tree with three starter skills unlocked.

They can click a starter skill and read its lesson in a left-side card.

They can manually mark that skill complete.

Progress saves to a JSON file on the server.

Completing a skill unlocks the next linked skill or skills.

Refreshing the browser preserves completed and unlocked skills.

Academy code is cleanly separated from Samba and Tailscale logic.

No arbitrary command execution is introduced.
