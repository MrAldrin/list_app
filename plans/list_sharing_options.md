# List Sharing From Mobile Home Screen (No Visible URL)

## Problem Summary
When the app is opened from a phone home screen (PWA style), the browser URL bar is hidden.
That makes it hard to share the current list link, even though lists are intentionally shareable without a password.

## Goal
Add a simple, reliable way for users to share the current list URL.

## Option 1: Copy Link Button (Clipboard Only)
### What it is
A `Copy link` button on the list page that copies the current URL to the clipboard.

### Pros
- Very simple to build and test.
- Works in most modern browsers.
- Clear behavior for users.

### Cons
- On phones, users still need to switch apps and paste manually.
- Feels less native than phone share sheets.

### MVP complexity
Low.

## Option 2: Native Share Button Using Web Share API
### What it is
A `Share` button that opens the phone’s native share sheet (`navigator.share`) where supported.

### Pros
- Best phone experience (Messages, Mail, apps, etc. in one tap).
- Ideal for home-screen/PWA usage.
- Very intuitive for non-technical users.

### Cons
- Not supported on every desktop browser.
- Requires fallback behavior when unsupported.

### MVP complexity
Low to medium (because fallback is required).

## Option 3: Share Dialog With URL + Copy + Manual Instructions
### What it is
A dialog/popover showing:
- the full list URL,
- a `Copy` button,
- small text guidance like “Send this link to anyone you want to share with.”

### Pros
- Works everywhere.
- Teaches users what is being shared.
- Easy to extend later (e.g., QR code).

### Cons
- Extra taps compared to native share sheet.
- Less “mobile-native” feel.

### MVP complexity
Low.

## Option 4: QR Code Share
### What it is
Show a QR code for the current list URL in a modal.

### Pros
- Useful for sharing between nearby devices.
- Nice extra option for in-person sharing.

### Cons
- Not the primary flow for most users.
- Adds extra dependency/UI complexity.

### MVP complexity
Medium.

## Recommendation (Best Option)
Use a **hybrid approach**:
- One `Share` button on the list page.
- Try native share first (`navigator.share`) when available.
- If unavailable (or share fails), open a simple dialog with:
  - the URL,
  - `Copy link` button.

Why this is best:
- Gives the smoothest mobile experience (your current pain point).
- Still works on desktop and unsupported browsers.
- Keeps implementation small and easy to understand for MVP.

## Suggested UX Text
- Button label: `Share`
- Success toast: `Link copied`
- Dialog title: `Share this list`
- Helper text: `Anyone with this link can open this list.`

## Simple Implementation Notes
In web development terms:
- `navigator.share(...)` asks the operating system to open the native share menu.
- `navigator.clipboard.writeText(...)` copies text to clipboard.
- We can call both from a button click and branch by feature support.

Pseudo-flow:
1. Build `share_url` from current list route.
2. If `navigator.share` exists, call it.
3. If not, show dialog with URL and `Copy link`.
4. On copy success, show short confirmation toast.

## Architecture Check
This change does not conflict with current architecture decisions.
It is a UI capability on top of existing share-by-URL behavior.

## Rollout Suggestion
1. Implement hybrid `Share` button for list page only.
2. Add a tiny test for share URL generation logic (if extracted into helper).
3. Optionally add QR code later if users request it.

## Progress Tracking
- [x] Define problem and constraints.
- [x] Compare multiple solution options.
- [x] Select recommended solution for MVP.
- [x] Implement UI changes.
- [ ] Test on mobile home-screen install and desktop fallback.
