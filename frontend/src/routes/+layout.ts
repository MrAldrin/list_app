// SPA mode: pages render only in the browser, and nothing is prerendered.
// The Python server sends the same index.html for every /app/ URL.
export const ssr = false;
export const prerender = false;
