import prettier from 'eslint-config-prettier';
import oxlint from 'eslint-plugin-oxlint';
import oxlintConfig from './.oxlintrc.json' with { type: 'json' };
import path from 'node:path';
import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import { defineConfig, includeIgnoreFile } from 'eslint/config';
import globals from 'globals';
import ts from 'typescript-eslint';

const gitignorePath = path.resolve(import.meta.dirname, '.gitignore');

export default defineConfig(
	includeIgnoreFile(gitignorePath),
	js.configs.recommended,
	ts.configs.recommended,
	svelte.configs.recommended,
	prettier,
	svelte.configs.prettier,
	{
		languageOptions: { globals: { ...globals.browser, ...globals.node } },
		rules: {
			// typescript-eslint strongly recommends not using the `no-undef` rule in TypeScript projects.
			// See: https://typescript-eslint.io/troubleshooting/faqs/eslint/#i-get-errors-from-the-no-undef-rule-about-global-variables-not-being-defined-even-though-there-are-no-typescript-errors
			'no-undef': 'off'
		}
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: {
			parserOptions: {
				projectService: true,
				extraFileExtensions: ['.svelte'],
				parser: ts.parser
			}
		}
	},
	// Oxlint scans Svelte scripts, not template expressions. Keep the existing
	// ESLint rules on .svelte files so those expressions still get checked.
	...oxlint.buildFromOxlintConfig(oxlintConfig, { withNursery: true }).map((config) => ({
		...config,
		ignores: [...(config.ignores ?? []), '**/*.svelte']
	}))
);
