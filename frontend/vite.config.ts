import adapterBun from '@sveltejs/adapter-bun';
import adapterStatic from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => ({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// The default build is still the SPA that Python serves from build/.
			adapter:
				mode === 'typescript-server'
					? adapterBun({
							out: 'build-ts',
							envPrefix: 'LISTR_TS_',
							serverOptions: { hostname: '127.0.0.1' }
						})
					: adapterStatic({ fallback: 'index.html' }),
			// The TypeScript hook enforces the exact origin for writes.
			// Run them before rejecting form bodies so the API can return its JSON error.
			csrf: { trustedOrigins: mode === 'typescript-server' ? ['*'] : [] },
			// The layout registers the worker after the legacy /sw.js cleanup gate.
			serviceWorker: { register: false },
			// The worker serves the root shell at deep links too. Its assets must
			// resolve from the origin, not the location of the current page.
			paths: { relative: mode !== 'typescript-server' }
		})
	],
	server: {
		proxy:
			mode === 'typescript-server'
				? undefined
				: {
						// The dev server forwards API calls to the Python app, so the browser
						// sees one origin and cookies work. The Host header is kept
						// (no changeOrigin), so the server's same-origin check still passes.
						// Responses are streamed as they arrive, so Server-Sent Events work too.
						'/api': { target: 'http://localhost:8080' },
						// Home-screen install: Python makes the manifests and serves the icons.
						'^/(manifest\\.webmanifest|room-manifest/)': { target: 'http://localhost:8080' },
						'/static/icons/': { target: 'http://localhost:8080' }
					}
	},
	// Tests use Svelte's browser code, as the app does (it never runs on a server).
	resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
	test: {
		// Reuse transforms between test runs; a clean install clears this ignored cache.
		fsModuleCache: true,
		include: ['src/**/*.test.ts']
	}
}));
