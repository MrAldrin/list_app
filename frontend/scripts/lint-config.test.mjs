import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { ESLint } from 'eslint';
import oxlintConfig from '../.oxlintrc.json' with { type: 'json' };

const cwd = fileURLToPath(new URL('../', import.meta.url));
const eslint = new ESLint({ cwd });
const sveltePath = 'src/lib/list/ListView.svelte';

function active(setting) {
	return (
		setting !== undefined && ![0, 'off'].includes(Array.isArray(setting) ? setting[0] : setting)
	);
}

function eslintNames(name) {
	return name.startsWith('typescript/')
		? [name.replace('typescript/', '@typescript-eslint/')]
		: [name, `@typescript-eslint/${name}`];
}

function oxlint(source, extension) {
	const directory = mkdtempSync(path.join(cwd, 'lint-probes-'));
	try {
		const filename = path.join(directory, `probe.${extension}`);
		writeFileSync(filename, source);
		const result = spawnSync(
			process.execPath,
			['node_modules/oxlint/bin/oxlint', '--no-ignore', '--format', 'json', filename],
			{ cwd, encoding: 'utf8' }
		);
		assert.ifError(result.error);
		assert.equal(result.signal, null, result.stderr);
		const output = JSON.parse(result.stdout);
		assert.equal(output.number_of_files, 1, result.stdout);
		return { status: result.status, diagnostics: output.diagnostics };
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
}

for (const filename of [
	'eslint.config.js',
	'src/lib/list/items.test.ts',
	'src/lib/data/compat.svelte.ts'
]) {
	test(`mapped checks do not run twice on ${filename}`, async () => {
		const { rules } = await eslint.calculateConfigForFile(filename);
		const mapped = {
			...oxlintConfig.rules,
			...(filename.endsWith('.ts') ? oxlintConfig.overrides[0].rules : {})
		};
		for (const [name, setting] of Object.entries(mapped)) {
			if (!active(setting)) continue;
			for (const eslintName of eslintNames(name)) {
				assert.ok(!active(rules[eslintName]), `${eslintName} still runs on ${filename}`);
			}
		}
		assert.equal(rules['svelte/no-svelte-internal'][0], 2);
	});
}

test('mapped checks remain on Svelte files because Oxlint cannot check templates', async () => {
	const { rules } = await eslint.calculateConfigForFile(sveltePath);
	for (const [name, setting] of Object.entries(oxlintConfig.rules)) {
		if (!active(setting) || name === 'no-self-assign') continue;
		assert.ok(
			eslintNames(name).some((alias) => active(rules[alias])),
			`${name} lost on Svelte`
		);
	}
	assert.equal(rules['svelte/require-each-key'][0], 2);
	assert.equal(rules['svelte/no-at-html-tags'][0], 2);
});

test('Oxlint rejects unsafe optional indexing in TypeScript', () => {
	const result = oxlint(
		'declare const init: { headers: Record<string, string> } | undefined;\nexport const value = (init?.headers)["Content-Type"];',
		'ts'
	);
	assert.equal(result.status, 1);
	assert.ok(result.diagnostics.some(({ code }) => code.includes('no-unsafe-optional-chaining')));
});

test('ESLint still catches unsafe optional chains inside a Svelte template', async () => {
	const source =
		'<script lang="ts">let { value }: { value: { items: string[] } | undefined } = $props();</script><p>{(value?.items).join(",")}</p>';
	assert.equal(oxlint(source, 'svelte').status, 0);
	const [result] = await eslint.lintText(source, { filePath: sveltePath });
	assert.equal(result.fatalErrorCount, 0, JSON.stringify(result.messages));
	assert.ok(result.messages.some(({ ruleId }) => ruleId === 'no-unsafe-optional-chaining'));
});

test('ESLint still rejects raw HTML and unkeyed each blocks', async () => {
	const [result] = await eslint.lintText(
		'{@html "<b>unsafe</b>"}{#each [1] as item}<p>{item}</p>{/each}',
		{ filePath: sveltePath }
	);
	assert.equal(result.fatalErrorCount, 0, JSON.stringify(result.messages));
	for (const rule of ['svelte/no-at-html-tags', 'svelte/require-each-key']) {
		assert.ok(
			result.messages.some(({ ruleId }) => ruleId === rule),
			`${rule} not reported`
		);
	}
});

test('Svelte rules that apply to plain TypeScript still run there', async () => {
	const [result] = await eslint.lintText("import 'svelte/internal';", {
		filePath: 'src/lib/list/items.test.ts'
	});
	assert.ok(result.messages.some(({ ruleId }) => ruleId === 'svelte/no-svelte-internal'));
});

test('template references do not cause unused-variable false positives', async () => {
	const source = '<script lang="ts">const value = 1;</script><p>{value}</p>';
	assert.equal(oxlint(source, 'svelte').status, 0);
	const [result] = await eslint.lintText(source, { filePath: sveltePath });
	assert.deepEqual(result.messages, []);
});

for (const source of [
	'export function example(a, a) { return a; }',
	'export const value = 0123;'
]) {
	test(`Oxlint module parsing rejects ${source}`, () => {
		const result = oxlint(source, 'js');
		assert.equal(result.status, 1);
		assert.ok(result.diagnostics.length > 0);
	});
}
