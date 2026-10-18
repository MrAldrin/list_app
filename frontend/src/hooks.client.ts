// Runs in the browser before the app starts, so it also covers the first page
// load. See `lib/stale-build.ts`.
import { startStaleBuildReload } from '#lib/stale-build.ts';

startStaleBuildReload();

// Safari on the iPhone only applies the CSS `:active` (pressed) style when the
// page listens for touches. This empty listener turns it on, for example for
// the pressed list cards in app.css.
document.addEventListener('touchstart', () => {}, { passive: true });
