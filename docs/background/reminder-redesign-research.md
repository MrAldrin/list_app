# Reminder redesign: research and design evidence

Research date: 2026-11-03. Planning evidence, not implemented behavior.
The proposed behavior and delivery stages live in the
[reminder plan](../../plans/due-date-reminders.md). Current behavior remains in
[due-date reminders](../due-date-reminders.md).

## Conclusions

- Separate a due date, a reminder schedule and the notification channel.
  A date should not automatically cause an interruption on every visit.
- A persistent due overview complements scheduled alerts; it does not replace
  configurable reminder times. Multiple reminders and snooze are useful without
  exposing every setting in the normal item editor.
- Standards-based Web Push is feasible on Android and installed iPhone web
  apps. Delivery is best effort, not an alarm-clock guarantee.
- Use the existing FastAPI process and SQLite database for a durable scheduler.
  A separate Railway cron service is not needed for this small installation.
- This app has no individual accounts. Device-specific preferences, room
  authorization and subscription ownership must be designed explicitly.

## What established apps actually document

### Microsoft To Do

[Add due dates and reminders](https://support.microsoft.com/en-us/todo/add-due-dates-and-reminders-in-microsoft-to-do):

> Scheduled tasks will automatically appear in the Planned smart list, where
> you can see your tasks due today, tomorrow, and beyond.

The guide separately describes **Add due date** and **Remind me**, including
choosing a date and time for a reminder. This supports an always-available
planned view and a separate reminder control. It does not establish a
navigation-triggered warning or a particular cooldown.

### Todoist

[Introduction to reminders](https://www.todoist.com/help/todoist/features/introduction-to-reminders-9PezfU):

> When you add a date and time to a task, Todoist can automatically add a task
> reminder.

The same guide documents configurable automatic-reminder timing, disabling
those reminders, custom date/time or relative reminders, multiple custom
reminders, and mobile snoozing. It explicitly says web/desktop do not offer
its mobile snooze feature. Plan tiers and UI can change; they are not a reason
for ListR to copy Todoist's restrictions.

A dated task is not evidence that a person wants repeated warnings. Defaults
plus an explicit **Add reminder** control are a better model than a hardcoded
"tomorrow or earlier" toast.

### Apple Reminders

The [iPhone guide](https://support.apple.com/en-us/102484) and
[Smart Lists guide](https://support.apple.com/guide/iphone/use-smart-lists-iphe882772ed/ios)
appeared in official-source search results describing daily notification
settings and Today/Scheduled views. The iPhone guide returned HTTP 429 when
fetched. Treat those details as search-level evidence only; the recommended
schedule below does not depend on a claimed Apple default.

### What this research does not establish

No checked competitor source establishes a universal ten-minute cooldown,
ten-notification daily cap, 22:00–08:00 quiet hours, or an ideal number of
reminders. These are proposed ListR defaults, adjustable by the user. Do not
present them as measured best practices or copy an old Todoist default from
an unrelated historical guide.

## Simplicity and accessibility

[Nielsen Norman Group: Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/):

> Initially, show users only a few of the most important options.
> Offer a larger set of specialized options upon request.

Recommendation: one visible reminder summary and one advanced editor, not a
large settings form in every item dialog. Inheritance may have three scopes
(device's room defaults, list, item), but do not require three nested dialogs
to inspect the effective setting.

[WAI alert pattern](https://www.w3.org/WAI/ARIA/apg/patterns/alert/) says alerts
must not move keyboard focus, warns against alerts that disappear
automatically, and notes that frequent interruptions inhibit usability.
[WCAG use of color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html)
requires another visual means of conveying information besides color.
[Status messages](https://www.w3.org/WAI/WCAG21/Understanding/status-messages.html)
explains programmatically identifiable messages without moving focus.

Recommendation: persistent due information, readable text alongside urgency
colors, a keyboard-accessible panel, and polite, restrained announcements.
An eight-second toast is not automatically proof of a WCAG failure; its
content and whether it remains available elsewhere matter.

## Phone-platform evidence

### iPhone and iPad

[WebKit's iOS/iPadOS 16.4 announcement](https://webkit.org/blog/13878/):

> A web app that has been added to the Home Screen can request permission to
> receive push notifications as long as that request is in response to direct
> user interaction.

The announcement also documents standard Web Push, Focus integration,
badging, and no requirement for Apple Developer Program membership. It is a
baseline compatibility statement, not a claim that every later feature works
on every iPhone.

Newer evidence was checked rather than relying only on the 2023 announcement:

- [Meet Declarative Web Push](https://webkit.org/blog/16535/) documents
  `userVisibleOnly: true` and says **no silent push messages are allowed**.
  Failure to display a notification in the original service-worker model can
  cause subscription revocation.
- [Safari 18.4 features](https://webkit.org/blog/16574/webkit-features-in-safari-18-4/)
  confirms Declarative Web Push for Home Screen web apps on iOS/iPadOS 18.4.
- The declarative format includes enough visible content and a navigation URL
  for the browser to display a notification even if worker code fails. WebKit
  describes using that same JSON with a service-worker fallback on older
  browsers. It is an enhancement, not a new minimum supported iOS version.
- Declarative subscriptions can survive removal of worker code. Server-side
  enrollment revocation is therefore essential; worker cleanup alone is not
  an authorization boundary.

The [current Apple developer guide](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)
also appeared in search results with the visible-notification requirement,
but direct fetching returned a JavaScript-only page. The fetched 2025 WebKit
articles provide the primary evidence for that requirement here.

### Android and other browsers

[MDN Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API) and
[web.dev subscription guide](https://web.dev/articles/push-notifications-subscribing-a-user)
describe secure contexts, service-worker subscription, permission and feature
detection. Android Chrome can support Web Push without requiring a Home
Screen install. Other browsers and embedded web views need feature checks;
"Android" alone is not a support guarantee.

The web.dev guide says that after a user blocks permission, the app cannot
simply ask again; the person must change the browser setting. Permission
should be requested only from a clear, deliberate enable action.

Do not require notification action buttons, a custom sound, vibration,
`requireInteraction`, or app-icon badges for core functionality. Support and
OS behavior vary. Ordinary notification tap-to-open plus in-app snooze is the
cross-platform baseline. Focus, battery settings, network availability and
system notification settings can delay or prevent delivery.

## Push transport, duplication and privacy

[MDN push best practices](https://developer.mozilla.org/en-US/docs/Web/API/Push_API/Best_Practices):

> Every push notification should be useful and time-sensitive ... [users]
> should ... be offered an easy way to opt out.

[Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API) describes
subscription endpoints as capability URLs that must be protected. Encryption
keys, endpoint URLs and VAPID private keys must not appear in logs or public
feeds. The application still needs its own same-origin write checks and
subscription ownership checks.

[RFC 8030 §5.2–5.4](https://datatracker.ietf.org/doc/html/rfc8030#section-5.2)
was fetched in full. It requires a TTL header, allows a push service to retain
messages for less time than requested, and forbids delivery attempts after
TTL expiry. Urgency is a transport hint; a Topic can replace a pending message
with the same topic. None of these provides exactly-once application delivery.

Recommendation: a durable outbox, stable occurrence IDs, bounded retries,
short expiry and replacement/deduplication tags. A timeout after sending is
ambiguous: the provider may already have accepted the message. Distinguish
"accepted by push service" from "delivered", "displayed" and "read".

Never use silent push to avoid foreground duplicates. Decide the transport
on the server before sending; every received push must have a visible fallback.
Once a message leaves the server, completion or access revocation cannot
reliably recall it. Generic lock-screen text is the safer default.

## Hosting recommendation

The repository already has a FastAPI lifespan task for daily pruning in
`src/server.py`, one SQLite connection/lock, one instance, an existing app
worker at `/service-worker.js`, and a retired worker kill switch at `/sw.js`.
Extend those seams rather than introducing a broker or another application.

[Railway cron](https://docs.railway.com/cron-jobs) documents:

- Runs at least five minutes apart, in UTC.
- No guarantee of execution to the minute.
- A new run is skipped if the previous run is still active.

[Railway volumes](https://docs.railway.com/volumes/reference) says volumes do
not support replicas and prevent simultaneous active deployments mounted to
the same service. This is not evidence that a new cron service can share the
existing SQLite mount. Do not design around such sharing.

[Railway Serverless](https://docs.railway.com/deployments/serverless) says
services may sleep after inactivity and wake on traffic. An in-process timer
cannot wake its own sleeping service. Confirm Serverless is **off** before
claiming closed-app reminders are operational; changing that hosting setting
requires the approved rollout, not an assumption or artificial keepalive.

Recommendation: one supervised lifespan task wakes roughly every 60 seconds,
reconciles durable due work, and sends outside the database lock. Actual
runtime cost and the live Serverless setting were not inspected. Existing
budget limits still apply; no paid service or budget increase is authorized.

## Evidence limits and review

Two bounded Claude Haiku 5.5/high research children supplied UX and platform
reports. Parent review checked newer WebKit behavior, Railway sleep rules,
accessibility guidance and RFC TTL details directly. The children's suggested
five-/fifteen-minute loop was not treated as a constraint on an in-process
timer; Railway cron's limit does not apply to that timer.

No real device was subscribed, no notification was sent, and no application or
production configuration was changed. Desktop WebKit tests cannot prove real
iPhone background delivery. The implementation must report that boundary
honestly rather than requiring routine manual phone checks or claiming
unperformed verification.
