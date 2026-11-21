## Summary

**Recommendation: keep Svelte 5 and SvelteKit.** Keep SQLite and the current API as the comparison baseline.

React is a valid alternative. Its strongest case is access to a specific React component library or a team that already knows React. Neither is an established requirement here. Popularity and podcast preference are not enough to justify a rewrite.

ListR already has strict TypeScript, component-local code and styles, offline storage, queued writes, live updates, and browser tests. React would not add these automatically. It would require new UI and state integration around much of the same application logic.

**Backend TypeScript benefits do not require a frontend rewrite.** Svelte can import browser-safe TypeScript schemas and functions. Runtime validation can also be added while keeping Python.

This report completes the source-level research deliverable. It does not close the bead, establish independent-review approval, or approve implementation.

## Evidence

### 1. Baseline and method

- **Supplied baseline:** `3ff346236bb3efaa01d8ec2fe923f971c4797845`.
- **Workspace inspected:** `/home/hsa/projects/list_app-stack-lr-3ns`.
- Repository links below are relative to that workspace and use file line ranges.
- Shell and version-control commands were prohibited. I did not independently verify the checkout hash.
- I read the supplied bead and prerequisite summaries. I also read the full `lr-48d.json` and `lr-d80.json` reports where their evidence helped. I then inspected the decisive code and external sources myself.
- The required subagent diagnostic ran. No agents were launched.

The documented architecture is a browser-only Svelte app served by FastAPI, with SQLite, an existing JSON API, and offline editing: [ARCHITECTURE.md:11–29](ARCHITECTURE.md#L11-L29). Stack changes and implementation remain approval gates: [docs/scope.md:39–57](docs/scope.md#L39-L57).

### 2. What the podcast recommends

The prerequisite identifies the relevant Superlinear episode as *The Fall 2026 Workflow for Starting Projects with Coding Agents*. I directly inspected its [publisher-linked timestamped transcript](https://www.buzzsprout.com/2632181/19826193/transcript.srt).

At **45:36–46:27**, the speaker recommends React and Tailwind. His explanation is that layout, code, and styles stay together, making the application easier for people and agents to understand. At **56:02–56:24**, the transcript discusses React with Vite.

These passages establish a stack preference. They do not establish:

- A measured React advantage over Svelte.
- A comparison using this app’s offline workflows.
- A need for Next.js or another React-based full-stack framework.
- A demonstrated improvement in agent correctness or owner learning.

The claimed benefit of keeping code, markup, and styles together already exists in Svelte components. For example, [Dialog.svelte:9–124](frontend/src/lib/ui/Dialog.svelte#L9-L124) contains TypeScript, dialog markup, and local styles in one file. Tailwind is a separate styling choice, not a reason that the component framework must change.

The transcript is primary publisher material, but I did not compare it with the audio. Its wording may contain transcription errors.

### 3. Existing Svelte investment is functional, not just historical

The earlier move from NiceGUI addressed a concrete missing capability: running the interface without a server connection. The historical record says Svelte was chosen for readable components and service-worker support: [docs/background/svelte-frontend-rewrite.md:9–19](docs/background/svelte-frontend-rewrite.md#L9-L19). That history explains the decision; current source is the evidence for what must now be preserved.

| Existing part | Direct observation | React change cost |
|---|---|---|
| Build and routing | Static adapter, `index.html` fallback, explicit worker registration, and development API proxy. | Replace route conventions and build configuration; retain equivalent server behavior. |
| Shared list UI | Room and public-share pages use `ListView`, with different permission-related controls. | Translate components and preserve the same separation. |
| Reactive room state | Uses Svelte runes, `SvelteMap`, derived values, and a separate effect root. | Rewrite the reactive adapter or introduce a deliberate bridge. |
| Durable queue | Stores operations in IndexedDB, separates room/share keys, and retains rejection records. | Potentially reusable storage code, but not replaceable by React state alone. |
| Offline shell | Uses SvelteKit build manifests, versioned caches, and guarded worker activation. | Replace build-manifest integration and verify old/new version behavior. |
| Accessibility | Native modal dialog, focus restoration, named controls, and keyboard tests. | Preserve behavior and assertions rather than assuming a library supplies parity. |

Sources: [frontend/vite.config.ts:1–40](frontend/vite.config.ts#L1-L40), [room list page:7–55](frontend/src/routes/room/[slug]/list/[list]/+page.svelte#L7-L55), [share page:9–78](frontend/src/routes/share/[token]/+page.svelte#L9-L78), [room-store.svelte.ts:88–151](frontend/src/lib/data/room-store.svelte.ts#L88-L151), [queue-storage.ts:1–43](frontend/src/lib/data/queue-storage.ts#L1-L43), [frontend/src/service-worker.ts:1–116](frontend/src/service-worker.ts#L1-L116), [Dialog.svelte:27–56](frontend/src/lib/ui/Dialog.svelte#L27-L56), [browser_tests/test_svelte_accessibility.py:44–132](browser_tests/test_svelte_accessibility.py#L44-L132).

These are preservation obligations, not an argument that previous effort must always be kept. Replacement becomes reasonable if a concrete benefit exceeds its future cost. No such benefit was demonstrated here.

### 4. React and React-based frameworks are different choices

**React** supplies a component and rendering model. It does not itself choose routing, persistent storage, API validation, or offline replay. React’s [from-scratch guide](https://react.dev/learn/build-a-react-app-from-scratch) explicitly describes these additional choices.

| Option | Fit with the current architecture | Important limit |
|---|---|---|
| Keep SvelteKit SPA | Existing routes and static build remain. FastAPI serves UI and API. | Retains SPA startup and JavaScript-dependence costs. |
| React + Vite + client router | Could remain a static browser app served by FastAPI. | Must select and configure routing, worker integration, state subscriptions, and equivalent checks. |
| React Router Framework Mode, SPA | Officially supports one generated `index.html` and browser routing. Could retain the existing API and one production origin. | Root route is rendered at build time, so browser-only APIs need appropriate boundaries. Offline behavior still belongs to the app. |
| Next.js static export | Does not necessarily require a production Node server. | Dynamic routes without `generateStaticParams()` are unsupported. Arbitrary room slugs and share tokens are therefore not a drop-in match for ordinary exported dynamic pages. |
| React framework with runtime server features | Could add server rendering or server-side route handling. | Adds a runtime and changes boundaries. No inspected requirement calls for it. Server rendering does not replace offline browser execution. |

Official sources: [React new-app guide](https://react.dev/learn/creating-a-react-app), [React Router SPA mode](https://reactrouter.com/how-to/spa), [Next.js static exports and unsupported features](https://nextjs.org/docs/app/guides/static-exports).

The existing Docker image uses Node only to build frontend files. Production runs Python: [Dockerfile:1–23](Dockerfile#L1-L23). A static React choice could preserve that shape. React does not inherently require another production server, Vercel, or a backend rewrite.

The existing static-file handler also supplies cache policies, legacy redirects, and real 404 responses for missing JavaScript and worker files: [src/svelte_frontend.py:103–158](src/svelte_frontend.py#L103-L158). A replacement must preserve those behaviors while accounting for different asset paths.

SvelteKit’s [SPA documentation](https://svelte.dev/docs/kit/single-page-apps) warns about initial network round trips, SEO, and failure when JavaScript is unavailable. These are real trade-offs. React in the same SPA mode does not remove them. No ListR startup benchmark was run.

### 5. Offline state and live updates are application work

Three concrete workflows show where rewrite cost lies.

**A. Make an offline edit, reload, then reconnect.**

The queue retains operation IDs and sends in order. It retries selected failures, pauses on lost authorization, and stops on an incompatible API version. Storage separates `room:<slug>` from `share:<token>`: [write-queue.ts:1–34](frontend/src/lib/data/write-queue.ts#L1-L34), [queue-storage.ts:1–43](frontend/src/lib/data/queue-storage.ts#L1-L43).

The optimistic overlay also distinguishes operations that could count twice when a lost answer leaves the outcome uncertain: [overlay.ts:12–34](frontend/src/lib/data/overlay.ts#L12-L34). React does not supply these rules.

**B. Leave a page, receive a live update, then return.**

Room state must outlive the component that first opened it. The current store has a Svelte-specific lifetime solution, backed by a test that ends the creating effect and then applies another feed: [room-store.svelte.ts:88–109](frontend/src/lib/data/room-store.svelte.ts#L88-L109), [room-lifetime.svelte.test.ts:54–81](frontend/src/lib/data/room-lifetime.svelte.test.ts#L54-L81).

React offers [`useSyncExternalStore`](https://react.dev/reference/react/useSyncExternalStore) for external state. It requires subscriptions and stable immutable snapshots. This is a possible integration mechanism, not a drop-in replacement for Svelte runes.

**C. Reconnect after another device changed data or access.**

Live updates use browser `EventSource`, visibility events, and an explicit reconnect callback that revalidates access and refreshes before queued retries: [events.ts:1–57](frontend/src/lib/data/events.ts#L1-L57). The browser test blocks the feed after reconnect to check that an online signal alone does not release writes: [test_svelte_offline_reconnect.py:137–170](browser_tests/test_svelte_offline_reconnect.py#L137-L170). This is test source, not a passing result from this session.

A library could reduce some state-management work. It would not automatically preserve these contracts. For example, TanStack Query documents persisted offline mutations, but also requires restoring mutation functions after reload and uses parallel mutations by default unless given a shared scope: [React mutation guide](https://tanstack.com/query/latest/docs/framework/react/guides/mutations).

TanStack Query also has a [first-class Svelte adapter](https://tanstack.com/query/latest/docs/framework/svelte/overview). Access to that library is not itself a React-only capability.

The current app has no background synchronization: changes are sent when the app can run and confirms access. See [docs/offline-viewing.md:30–39](docs/offline-viewing.md#L30-L39). Changing the component framework does not change browser background-execution limits.

### 6. Ecosystem and accessibility: a real argument for React, but not yet a requirement

React provides access to React-specific libraries. A concrete example is [Adobe React Aria](https://react-aria.adobe.com/), which documents accessible components, keyboard and touch behavior, focus management, internationalization, and advanced interactions such as drag-and-drop and multi-selection.

That could matter if the owner selects a complex interaction for which a particular library is clearly the best fit. It is stronger evidence than package counts. However:

- No approved requirement for those advanced interactions was supplied.
- Vendor descriptions are not proof of a successful ListR integration.
- Library use still requires correct labels, application behavior, styling, and tests.
- A focused integration or a browser-native alternative should be compared before replacing the entire UI.

ListR already uses native `<dialog>` behavior and explicit focus restoration. Browser tests inspect control names, dialog focus, and keyboard selection: [Dialog.svelte:27–56](frontend/src/lib/ui/Dialog.svelte#L27-L56), [test_svelte_accessibility.py:44–132](browser_tests/test_svelte_accessibility.py#L44-L132).

Svelte also supplies [compile-time accessibility warnings](https://svelte.dev/docs/svelte/compiler-warnings). Neither those warnings nor the current tests establish complete accessibility or screen-reader coverage. React alone establishes neither.

**Concrete missing-capability finding:** none was identified that requires React. This is a bounded finding about the inspected app and supplied requirements, not a claim that Svelte can satisfy every future need equally well.

### 7. Agent feedback and owner learning

The frontend already enables strict TypeScript and provides scripts for formatting, linting, Svelte/type checks, unit tests, and builds: [frontend/tsconfig.json:1–8](frontend/tsconfig.json#L1-L8), [frontend/package.json:6–16](frontend/package.json#L6-L16). ESLint includes TypeScript and Svelte recommended configurations: [frontend/eslint.config.js:1–35](frontend/eslint.config.js#L1-L35).

React has useful framework-specific checks too. Its official [Hooks ESLint plugin](https://react.dev/reference/eslint-plugin-react-hooks) checks hook rules, dependencies, purity, and other supported patterns. These are genuine feedback mechanisms. They are not evidence that React agents make fewer mistakes on ListR.

There are learning costs on both sides:

- Svelte has compiler-specific syntax, runes, and effect-lifetime rules. The existing lifetime test illustrates a real subtlety.
- React introduces JSX, render/state rules, Hooks, effect dependencies, and a new integration approach for the existing long-lived room state.
- A React full-stack framework adds further server/client and rendering concepts.

React may be preferable for learning goals centered on React employment or a React team. No such goal was supplied. For this owner’s current app, translating working components adds learning work before any demonstrated feature gain.

No controlled agent comparison, owner comprehension exercise, or maintenance-time measurement was performed. Model familiarity and training-data claims remain hypotheses.

### 8. Backend TypeScript does not require React

The existing UI already uses TypeScript. Svelte’s [official TypeScript guide](https://svelte.dev/docs/svelte/typescript) supports typed components and command-line checks.

A separately approved TypeScript backend could share browser-safe request/response schemas and selected pure functions with this Svelte UI. A schema library such as [Zod](https://zod.dev/) documents support for Node and modern browsers; it is not tied to React.

Keep server credentials, database access, and authorization logic out of shared browser modules. SvelteKit documents [server-only module boundaries](https://svelte.dev/docs/kit/server-only-modules), including the important limit that illegal-import detection is disabled in unit-test mode.

Even keeping Python, generated browser declarations and runtime validation remain options, as the `lr-d80` prerequisite explains. A frontend rewrite is not necessary to address the observed unchecked response boundary: `Api.request<T>` returns parsed JSON through `data as T`: [api.ts:64–103](frontend/src/lib/data/api.ts#L64-L103).

Do not add a write decoder casually. The current queue removes an operation on non-retryable exceptions: [write-queue.ts:414–449](frontend/src/lib/data/write-queue.ts#L414-L449). A malformed successful answer may follow a committed write. Validation must preserve that unknown outcome rather than report that nothing was saved. The reminder adapter already names this distinction: [reminders/api.ts:26–33](frontend/src/lib/reminders/api.ts#L26-L33).

This is a contract-design issue, not evidence for React.

## Arguments for and against

### Keep SvelteKit

**Strongest arguments for:**

- Fits the existing small, mobile, offline app and one-origin deployment.
- Preserves current UI behavior, state integration, worker handling, and tests.
- Already provides typed components, local styles, routing, and development feedback.
- Allows backend TypeScript or stronger contracts without replacing the UI.

**Strongest arguments against:**

- Svelte-specific reactivity and compiler tooling require knowledge and maintenance.
- Some valuable UI libraries expose React-only interfaces.
- The present SPA has startup and JavaScript-dependence costs that deserve measurement if users report problems.
- Existing code is not automatically simpler merely because it is already implemented.

### Change to React

**Strongest arguments for:**

- Direct use of a selected React-specific component library could reduce difficult interaction work.
- React-skilled collaborators could maintain a familiar stack.
- Hooks and compiler-related diagnostics offer useful feedback.
- A static React architecture could keep Python, SQLite, the API, and the current production process shape.

**Strongest arguments against:**

- No required missing capability or measured advantage was established.
- Components, routing, reactive state integration, and worker build integration need replacement or adaptation.
- Offline correctness and access rules remain application responsibilities.
- New abstractions add owner learning and review cost.
- Choosing a full-stack React framework can expand the change beyond the frontend without a corresponding need.

## Recommendation

1. **Keep SvelteKit. Do not start a React rewrite.** Confidence is high that the supplied evidence does not justify replacement. Confidence is lower about future library needs and comparative maintenance cost.
2. **Keep frontend and backend decisions separate.** React is not a dependency of strict TypeScript, shared schemas, runtime validation, or a TypeScript API.
3. **Prioritize the known contract problem through its existing task owner.** Preserve queue recovery and storage compatibility. Do not introduce another state library as an unstated part of that work.
4. **Reopen the React question only for a named need.** Examples could include an approved complex interaction, a required React-only integration, or a clear team/learning objective. These are decision triggers, not current requirements.
5. **If a comparison is later approved, keep it narrow.** Compare the same small feature in the current Svelte setup and a named React setup. Measure owner review effort, agent correction cycles, equivalent check time, bundle/startup impact, and integration work. Do not change backend language, API behavior, or storage at the same time.

Any later replacement proposal must explain how it preserves queued operation IDs and bodies, room/share storage separation, authorization revalidation, page lifetime, public-link controls, and installed-app updates. Test old saved data and an already-open old app version; a fresh install alone is insufficient evidence of compatibility.

These are proposed comparison criteria, not executed results or new deployment gates. Keep the project’s existing automated release process. Do not add staging or routine manual-device gates.

## Unknowns

- Checkout identity and installed package versions were not independently verified.
- No tests, type checks, lint checks, builds, browser sessions, or performance measurements were run.
- No React prototype was built. Rewrite effort and reusable-code proportions are not measured.
- The podcast transcript was not checked against audio.
- Comparative agent reliability and owner learning cost remain unmeasured.
- No complete accessibility audit or assistive-technology comparison was performed.
- No required React-only integration was supplied. Future ecosystem needs may change the decision.
- Framework documentation describes current mechanisms, not verified compatibility with a pinned ListR trial.
- Service-worker transition, saved-storage compatibility, and browser bundle costs for a React replacement remain untested.

## Handoff

**Runner and reviewer:** independently review this report. `status: complete` means the research deliverable is ready, not that review passed or the bead was closed.

**Next stack-decision task:** carry forward the keep-Svelte recommendation separately from the backend language decision. Use the existing offline-edit, reconnect, page-lifetime, and public-share workflows as fixed behavior. A whole-stack preference is not a measured benefit.

**Owner relay to contract work:** the prerequisite identifies `lr-347.4.3` as related contract work. Relay the unchecked response boundary and unknown-write-outcome requirement. Live ownership was not checked in this read-only session. Keep detailed contract and checker audits with that task.

**Future React proposal, if requested:** first name the missing capability and the exact React setup. Compare its total maintenance benefit with a focused Svelte or browser-native solution before proposing replacement.

**Execution record:** no files, frontend code, packages, Beads records, version-control state, or deployment state were changed. No shell commands, servers, or agents were started. Only source/web research and the required subagent diagnostic were performed.
