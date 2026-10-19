# ListR feature research: what list and grocery apps offer

Date of research: 2026-10-19. Sources are listed at the end.

## Caveats

- Reddit was blocked for the search tool, so this has no direct Reddit evidence.
- Most complaint evidence comes from app-store aggregator sites, which are weak.
- Competitor comparison pages (Listonic) are marketing. Treat their claims as claims.
- A "?" in the matrix means the sources I could read did not say. It does not mean "no".

## 1. Feature matrix

Key: Y = yes, P = paid tier, N = no, ? = not found in sources.

| App | Shared | Aisle or store sort | Recipe import | Meal plan | Price | Barcode | Voice | Widget | Offline | Self-host | AI |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AnyList | Y | Y (custom categories) | P (5 free, unlimited paid) | P | P (running totals) | ? | Y (Siri, Alexa) | Y | ? | N | ? |
| Bring! | Y (real-time) | Y (any order, incl. aisles) | Y (save from web) | ? | ? | ? | Y (Siri, Google, Alexa) | Y (iOS, Watch) | ? | N | ? |
| OurGroceries | Y (all or nothing) | ? | ? | ? | ? | ? | Y (Alexa) | ? | ? | N | N |
| Out of Milk | Y | ? | ? | ? | P (totals, tax) | ? | Y (Alexa, Google Home) | P (add-on) | ? | N | N |
| Listonic | Y | Y | ? (recipe keeper on Play) | ? | Y (total cost) | ? | ? | ? | ? | N | N |
| Google Keep | Y (checklist) | N (per one review) | N | N | N | N | Y (Assistant) | ? | Y | N | Y (Gemini list builder) |
| MS To Do | Y | ? | N | N | N | N | ? | ? | ? | N | Copilot grocery: not found |
| Apple Reminders | Y | Y (grocery categories) | N | N | N | N | Y (Siri) | ? | ? | N | N |
| Todoist | Y | ? | N | N | N | N | ? | ? | ? | N | N |
| Paprika | ? | Y (custom aisles) | ? | Y | ? | ? | N | N | ? | N (own sync) | N |
| Mealie | Y (households) | Y (follows store layout) | Y (URL) | Y | ? | ? | N | N | N (per review) | Y | ? |
| Grocy | ? | Y (assortment groups) | N | Y | Y (price history) | Y (camera, USB, Open Food Facts) | N | N | Y (Android app) | Y | N |
| KitchenOwl | Y (real-time) | ? | Y (built-in parser) | Y | Expenses Y | ? | ? | ? | Partial | Y | ? |

Other notes:

- Urgency labels (urgent, if convenient, on offer): Bring!
- Duplicate or past-item autocomplete: OurGroceries, AnyList ("recently used", favorites), Listonic (suggests frequent items first).
- Pantry or stock with expiry: Grocy, Paprika, Listonic, Out of Milk, Shopping Share.
- Recurring lists (weekly or monthly repeat): Shopper (App Store listing).
- Activity history of who changed what: Shopper.
- Photos on items: Bring!, Listonic, AnyList Complete.
- Paste text to list with review before adding: Smart and Simple, DishPal, Recipe to Grocery List (iOS apps, developer claims only).
- Telegram bots for lists (open source): OpenMemo, ListManager (also an Alexa skill), EggCart, PickMe. No email-to-list project found.
- Location reminders: Todoist (paid, per an older APK listing), AnyList (listed, tier unclear). Apple Reminders not confirmed in my sources.

## 2. Complaints and requests (thin evidence)

- Bring!, 2014: it made shared lists paid, then reversed it after many angry comments. Users said "Abzocke 2.0" (scam 2.0). Source: appgefahren.de.
- Bring!, recent: a German reviewer says Premium (about 14 EUR per year) removes ads, but the "Inspiration" and "Angebote" promo prompts stay. Users say the app feels overloaded. Source: mobiFlip.
- OurGroceries: sharing is all or nothing, so you cannot share one list and keep another private. One review reported duplicate items after an edit. Source: justuseapp.
- AnyList: Trustpilot is mixed. Complaints are about features not matching promises and support. Source: Trustpilot.
- Out of Milk: one aggregator reports data loss and sync problems after updates. This is weak evidence. Source: Android Central review, aggregator pages.
- Mealie: no offline mode, import inconsistent on small blogs, database migrations sometimes fail, setup is hard for non-technical users. Source: Cooklang review (competitor author).
- KitchenOwl: still in development. The README does not say which stage (alpha, beta) it is in. Source: GitHub README.
- Grocy: the Railway template ships with default admin/admin credentials. Source: railway.com template page.
- Google Keep: limited for aisle sorting, barcode, price, and meal plans. Source: Android Central tests.
- Requests seen across sources: quantities, separate lists per store, price entry, widgets, data import and export, Assistant integration that breaks, and reliable real-time sync.

## 3. Feature ideas for ListR (23)

Effort scale for this stack (FastAPI, SQLite, Svelte PWA): S = under 1 day, M = a few days, L = 1 to 2 weeks, XL = multi-week, or needs a new platform.

Note: ListR has no user accounts. Features that need "who" beyond a typed device name need user profiles (already in the backlog Ideas).

### Small polish

1. **Usual items and autocomplete from history.** Suggest items you add often and match as you type. Uses the existing "times added" counter. Value: high, saves typing on a phone. Effort S to M. Apps: Listonic, OurGroceries, AnyList. Deps: none.
2. **Per-item notes and units.** Short note such as "the green one" or a unit such as "kg". Value: medium. Effort S. Apps: AnyList, Bring!, Out of Milk. Deps: none.
3. **Urgency labels.** Mark an item "urgent", "if convenient" or "on offer". Value: low to medium. Effort S. Apps: Bring!. Deps: none.
4. **Longer undo.** Already in backlog. Value: medium. Effort S. Apps: general. Deps: none.

### Medium

5. **Store profiles with aisle order.** One list can use a store profile. Drag sections into your store's order, and tags become aisles. Value: very high for shoppers. Effort M. Apps: Bring!, AnyList, Listonic, Paprika, Grocy, Mealie, Apple Reminders. Deps: extends current sorting.
6. **Recurring items.** Items that come back each week, or a reset to a saved template. Value: high for a family. Effort M. Apps: Shopper, Grocy (auto-add when low). Deps: a server-side timer.
7. **"I'm shopping" status.** One person marks "I am at the store". Others see it live over the existing stream. Stops double-buying. Value: high. Effort S to M. Apps: none found directly; Shopper and Shopping Share describe shared lists for couples. Deps: a name typed on the device, not accounts.
8. **Activity history.** Show who added, checked or removed each item and when. Value: medium. Effort M. Apps: Shopper. Deps: the backlog item "timestamps and change versions".
9. **Share target from other apps.** Use the phone share sheet to send a link or text to ListR. Value: medium. Effort S to M. Apps: none checked. Deps: works on Android Chrome. iOS support not verified.
10. **Photos on items.** A picture of the exact product. Value: low to medium. Effort M. Apps: Bring!, Listonic, AnyList Complete. Deps: image storage on the Railway volume.
11. **Barcode scan.** Scan with the phone camera, then look up the name with Open Food Facts. Value: low for a 5-person list. Effort M. Apps: Grocy, KitchenOwl (listed, not confirmed). Deps: a browser barcode API or a JS library. Browser support is uneven; not verified on iOS.
12. **Price per item and running total.** Remember last price per store and show the total. Value: medium for budgets. Effort M. Apps: Listonic, AnyList Complete, Out of Milk, Grocy. Deps: new price fields.

### Large

13. **Paste text to list.** Paste a message, recipe, or note. Split it into items and let the user confirm. Start with simple rules (S). Add an AI parser later (M to L, with API cost). Value: high. Apps: Smart and Simple, DishPal, Recipe to Grocery List. Deps: none for rules. AI needs an API key and a privacy check.
14. **Recipe URL import to list.** Paste a recipe link, get ingredients, add them to a list in one tap. Value: high for cooks. Effort L. Apps: AnyList, Bring!, Mealie, KitchenOwl, Paprika. Deps: recipe storage. Mealie shows imports are inconsistent on small sites, so expect cleanup.
15. **Meal plan to list.** Pick dinners for the week, then generate one combined list. Value: medium to high. Effort L. Apps: AnyList, Paprika, Mealie, KitchenOwl, Grocy. Deps: idea 14 is the usual base.
16. **Pantry with auto-add when low.** Track what is at home and auto-add items below a minimum. Value: medium. Effort L. Apps: Grocy, Paprika, Listonic. Deps: quantities already exist.
17. **Telegram bot.** Add items and read the list in a chat. Value: medium. Effort M. Apps: OpenMemo, ListManager, EggCart, PickMe (open source). Deps: linking a Telegram user to a room needs a secret link code, or user profiles.
18. **Email to list.** Forward an email to a room address and get items. Value: low to medium. Effort M. Apps: none found. Deps: an inbound email service and a per-room secret address.
19. **Voice add.** Phone keyboards already have dictation, so this is low value. The big version is an Alexa or Siri shortcut. Effort S for dictation, L for assistant skills. Apps: Bring!, AnyList, OurGroceries, Keep. Deps: assistant skill needs a public API endpoint and a token.
20. **Push notifications.** Notify when someone adds or checks an item. Value: medium. Effort M. Apps: Listonic (notifications), Shopper. Deps: web push on iOS works only for installed home-screen apps. Must not break the `/sw.js` kill switch in the backlog.

### Crazy

21. **Native app wrapper.** Wrap the PWA in a native shell (for example Capacitor). Gives widgets, store geofences, and easier assistant integration. Effort XL. Apps: Bring!, OurGroceries, AnyList, Out of Milk (widgets). Deps: an ARCHITECTURE decision, since it is a stack change.
22. **Home-screen widget.** Show the list on the home screen. Effort XL on iOS (needs the native shell). Apps: Bring!, OurGroceries, AnyList. Deps: idea 21.
23. **Store geofence reminder.** Notify when near a store. Value: medium. Effort XL. Apps: Todoist (paid), Apple Reminders. Deps: idea 21 and location permission.

## 4. Top 5 picks and why

1. **Store profiles with aisle order (idea 5).** Shoppers use it every trip. Almost every serious app has it. It builds on the sorting that already exists. Effort M.
2. **Usual items and autocomplete (idea 1).** The "times added" counter is already there, so the data exists. Cuts typing on a phone. Effort S to M.
3. **"I'm shopping" status (idea 7).** Fits five people in the same house. Solves double-buying. Live updates already exist. No accounts needed. Effort S to M.
4. **Paste text to list, rules first (idea 13).** Fast to build, and it covers recipes and chat messages without a full recipe system. Add AI later only if rules are not enough. Effort S.
5. **Recipe URL import to list (idea 14).** The top feature of AnyList and Bring!, and the base for meal plans. Start after idea 13. Expect messy imports, as Mealie users report. Effort L.

Pushback:

- Skip barcode and price tracking for now. A five-person family list gets little from them.
- Skip a native app until a widget or geofence is really needed. It is the biggest stack change.
- Recurring items (idea 6) may beat recipe import for this group. Ask the users which they use more.

## Sources

- AnyList App Store: https://apps.apple.com/app/anylist/id522167641
- AnyList features (fetched): https://www.anylist.com/features
- AnyList Trustpilot: https://www.trustpilot.com/review/anylist.com
- AnyList AlternativeTo: https://alternativeto.net/software/anylist/about
- Bring! features: https://www.getbring.com/en/features
- Bring! 2014 subscription reversal: https://www.appgefahren.de/?p=114815
- Bring! 2014 subscription article: https://www.appgefahren.de/?p=273515
- Bring! Premium review (mobiFlip): https://www.mobiflip.de/shortnews/bring-einkaufsliste-premium/amp/
- OurGroceries reviews (justuseapp): https://justuseapp.com/en/app/325851015/our-groceries-shopping-list/reviews
- OurGroceries overview (Chowhound): https://www.chowhound.com/1852927/grocery-list-apps/
- OurGroceries Reddit mirror thread (r/aldi): https://reddit.fabiomanganiello.com/r/aldi/comments/1gtilhh/shopping_list_app/lxmu6xi/?context=3
- Out of Milk (Android Central): https://androidcentral.com/out-milk-review-now-you-have-no-excuse-forgetting-groceries
- Out of Milk (Push Interactions): https://pushinteractions.com/app-review-out-of-milk/
- Out of Milk (Softpedia): https://mobile.softpedia.com/android/Out-of-Milk-Android-Review-1462.html
- Listonic features: https://fpdev.listonic.com/features/total-cost
- Listonic vs OurGroceries (competitor page): https://fpdev.listonic.com/best-grocery-list-apps/listonic-vs-our-groceries
- Listonic vs Out of Milk (competitor page): https://listonic.com/compare-apps/listonic-vs-out-of-milk
- Google Keep Gemini list builder: https://www.sammobile.com/news/google-keep-create-lists-gemini-ai/
- Google Keep Pixel test (Android Central): https://www.androidcentral.com/phones/gemini-live-pixel-9-pro-grocery-list
- Microsoft To Do (Microsoft): https://www.microsoft.com/en-us/microsoft-365/microsoft-to-do-list-app
- Microsoft To Do tips: https://www.microsoft.com/en-us/microsoft-365-life-hacks/?p=471
- Apple Reminders grocery lists (Apple): https://support.apple.com/en-bw/guide/iphone/iph80ba26e1f/ios
- Apple Reminders grocery categories (9to5Mac): https://9to5mac.com/2023/06/09/ios-17-reminders-groceries/
- Todoist location reminders (Droid Life): https://www.droid-life.com/?p=145375
- Paprika 3 App Store: https://apps.apple.com/ae/app/id1303222868
- Mealie GitHub: https://github.com/mealie-recipes/mealie
- Mealie review (Cooklang, competitor): https://cooklang.org/blog/40-mealie-review/
- Grocy GitHub: https://github.com/grocy/grocy
- Grocy features: https://grocy.info/
- Grocy Railway template (default credentials): https://railway.com/deploy/grocy-inventory.md
- KitchenOwl GitHub: https://github.com/TomBursch/kitchenowl
- KitchenOwl overview (LinuxLinks): https://www.linuxlinks.com/kitchenowl/
- Tandoor release tracker: https://releasealert.dev/github/TandoorRecipes/recipes
- OpenMemo (Telegram, open source): https://github.com/haerincode/openmemo
- ListManager (Telegram and Alexa, open source): https://github.com/nicomanto/ListManager
- EggCart (Telegram, open source): https://github.com/ljgonzalez1/eggcart
- Shopping Share App Store (pantry, aisles, roommates): https://apps.apple.com/app/id1034363967
- Smart and Simple (paste text to list): https://apps.apple.com/app/id6758018547
- DishPal (paste recipe to aisle list): https://apps.apple.com/app/id6755170439
- Recipe to Grocery List: https://apps.apple.com/app/id6760125955
