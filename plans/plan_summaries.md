# Plan Analysis and Consolidation Recommendations

This document tracks the remaining feature plans in the `plans/` directory. All historically implemented architecture plans, PWA fixes, and security schemas have been merged into `ARCHITECTURE.md` or dedicated reference documents.

## 1. Core Features (Lists & Sharing)
*Feature specifications regarding how lists are created and shared among users.*

**Document:** `advanced_sharing.md`
**Overview:** An ambitious future feature allowing users to share an individual list with friends via "Share Tokens", and allowing those friends to "Pin" that list into their own private room dashboard.
**Status:** **Not Implemented**. The database does not yet support cross-room list pinning or share tokens.
**Recommendation:** **Keep**. This is a valid roadmap feature that hasn't been started yet.

---

## 2. Reference Documents
*These are not active plans, but rather technical context required for maintaining the app.*

**Document:** `pwa_ios_quirks_reference.md`
**Overview:** Explains why the root route (`/`) is decoupled from the admin panel (`/admin`), and how local storage is used to seamlessly route PWA users to their last visited room to avoid iOS Safari breaking standalone mode.
**Status:** Reference only. Keep indefinitely to prevent regressions.