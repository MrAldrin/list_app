// Runs in the browser before the app starts, so it also covers the first page
// load. See `lib/stale-build.ts`.
import { startStaleBuildReload } from '#lib/stale-build.ts';

startStaleBuildReload();
