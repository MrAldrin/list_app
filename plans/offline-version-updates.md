# Offline viewing: get new versions to phones quickly

Lifecycle: tracked

The last blocker before offline viewing goes live. Found during the Gate V
iPhone review on 2026-10-12.

## Problem

- The service worker keeps a complete copy of the app on the phone. A new
  version is downloaded in the background, but it only takes over after every
  open copy of the app is closed. On an iPhone the home-screen app and every
  Safari tab with the site count.
- Seen on the iPhone: after a new local build, killing the home-screen app was
  not enough; the old text stayed. Closing the browser too and opening again
  gave the new version.
- After each deploy, people can stay on the old version for a long time.
- Combined with the "A new version is available" banner (see
  [offline viewing](../docs/offline-viewing.md#after-a-deploy)): tapping Reload
  can load the old stored copy again. The banner returns and writes stay
  blocked until all copies are closed.
- Database migrations make this worse. When a deploy changes what the API
  means, the API version bump stops old pages from writing, which protects the
  data. But those people cannot edit until their phone switches version, so the
  switch must be fast.

## Options

1. **Reload switches version.** The banner's Reload button tells the waiting
   new version to take over, then reloads. Only helps people who see the
   banner.
2. **Switch on open (owner's likely choice).** When the app opens and a new
   version is waiting, switch to it at once, if no changes wait to be sent.
   Reload in the banner does the same. New versions then arrive on the next
   open, not after every copy is closed.

Open questions for the design: what happens to a page that is already open in
another tab when the version switches; how to keep an offline open safe (no
switch without a complete new copy); tests for both.

## Progress

- [x] Problem found and options written down (2026-10-12)
- [ ] Owner picks an option
- [ ] Build and test it
- [ ] Recheck on the iPhone
