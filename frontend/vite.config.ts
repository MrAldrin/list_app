import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// SPA mode: build plain static files into `build/`. Every URL the
			// server does not know falls back to `index.html`, and the router in
			// the browser picks the page.
			adapter: adapter({ fallback: 'index.html' }),

			// Python serves the built app under /app/ until the switch.
			paths: { base: '/app' }
		})
	],
	server: {
		proxy: {
			// The dev server forwards API calls to the Python app, so the browser
			// sees one origin and cookies work. The Host header is kept
			// (no changeOrigin), so the server's same-origin check still passes.
			// Responses are streamed as they arrive, so Server-Sent Events work too.
			'/api': { target: 'http://localhost:8080' }
		}
	},
	// Tests use Svelte's browser code, as the app does (it never runs on a server).
	resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
	test: {
		include: ['src/**/*.test.ts']
	}
});
