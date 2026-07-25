# Plan Analysis and Consolidation Recommendations

This document tracks the remaining feature plans in the `plans/` directory. All historically implemented architecture plans, PWA fixes, and security schemas have been merged into `ARCHITECTURE.md` or dedicated reference documents.

## 1. Core Features (Lists & Sharing)
*Feature specifications regarding how lists are created and shared among users.*

**Document:** `advanced_sharing.md`
**Overview:** An ambitious future feature allowing users to share an individual list with friends via "Share Tokens", and allowing those friends to "Pin" that list into their own private room dashboard.
**Status:** **Not Implemented**. The database does not yet support cross-room list pinning or share tokens.
**Recommendation:** **Keep**. This is a valid roadmap feature that hasn't been started yet.

---

## 2. Item Features (Quantities & UX Prototypes)

**Document:** `item_quantities.md`
**Overview:** Detailed plan for item quantities in SQLite & backend, with two Jujutsu (`jj`) workspaces (`prototype-inline` on port 8080 and `prototype-modal` on port 8081) for side-by-side UX evaluation on mobile.
**Status:** **Plan Created** (Ready for implementation).


---
*Note: Long-term reference documents and architecture notes are moved to `docs/` or `ARCHITECTURE.md` to keep `plans/` strictly for active implementation plans.*