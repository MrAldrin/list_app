import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, writeFileSync, symlinkSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import guard, { checkCall } from './stack_research_guard.mjs';

test('only manifest files can be read; symlink escape denied', () => {
  const root = mkdtempSync(join(tmpdir(), 'stack-guard-'));
  try {
    writeFileSync(join(root, 'allowed.py'), 'x = 1');
    writeFileSync(join(root, 'secret'), 'synthetic');
    symlinkSync(join(root, 'secret'), join(root, 'alias.py'));
    const config = { files: [join(root, 'allowed.py')] };
    assert.equal(checkCall('read', { path: 'allowed.py' }, root, config), null);
    assert.ok(checkCall('read', { path: 'secret' }, root, config));
    assert.ok(checkCall('read', { path: 'alias.py' }, root, config));
    assert.ok(checkCall('read', { path: '/etc/passwd' }, root, config));
    assert.ok(checkCall('grep', { path: '.' }, root, config));
    assert.ok(checkCall('bash', { command: 'true' }, root, config));
  } finally { rmSync(root, { recursive: true }); }
});

test('search forces OpenAI and rejects obvious private payloads', () => {
  const input = { query: 'Effect TypeScript typed errors', provider: 'auto', model: 'other' };
  assert.equal(checkCall('web_search', input, '/', {}), null);
  assert.equal(input.provider, 'openai');
  assert.equal(input.model, undefined);
  assert.ok(checkCall('web_search', { query: '/home/hsa/.env' }, '/', {}));
  assert.ok(checkCall('source_check', { claim: 'code { private }' }, '/', {}));
});

test('typing stop in interactive Pi stops the whole queue without another model call', () => {
  const root = mkdtempSync(join(tmpdir(), 'stack-stop-'));
  const old = process.env.LISTR_RESEARCH_GUARD;
  try {
    const config = join(root, 'guard.json');
    writeFileSync(config, JSON.stringify({ stop: join(root, 'STOP') }));
    process.env.LISTR_RESEARCH_GUARD = config;
    const hooks = {};
    guard({ on(name, handler) { hooks[name] = handler; } });
    let aborted = false;
    assert.deepEqual(hooks.input({ text: 'please stop now' }, { abort() { aborted = true; } }), { action: 'handled' });
    assert.equal(aborted, true);
    assert.equal(existsSync(join(root, 'STOP')), true);
  } finally {
    if (old === undefined) delete process.env.LISTR_RESEARCH_GUARD;
    else process.env.LISTR_RESEARCH_GUARD = old;
    rmSync(root, { recursive: true });
  }
});

test('only the runtime doctor management action is permitted', () => {
  assert.equal(checkCall('subagent', { action: 'doctor' }, '/', {}), null);
  assert.ok(checkCall('subagent', { agent: 'worker', task: 'launch' }, '/', {}));
  assert.ok(checkCall('subagent', { action: 'resume', id: 'x' }, '/', {}));
});

test('fetch allows public text but not local files, credentials or model-assisted modes', () => {
  for (const url of ['file:///etc/passwd', 'http://localhost/a', 'https://127.0.0.1/a',
    'https://[::1]/a', 'https://user:pass@example.com/a', 'https://youtube.com/watch?v=x']) {
    assert.ok(checkCall('fetch_content', { url }, '/', {}), url);
  }
  const input = { url: 'https://effect.website/docs/' };
  assert.equal(checkCall('fetch_content', input, '/', {}), null);
  assert.equal(input.redirects, 'same-origin');
  assert.ok(checkCall('fetch_content', { ...input, auth: true }, '/', {}));
  assert.ok(checkCall('fetch_content', { ...input, mode: 'answer' }, '/', {}));
});
