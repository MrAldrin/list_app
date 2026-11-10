// Explicitly loaded only by stack_research.py. No global Pi configuration changes.
import { readFileSync, realpathSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const WEB = new Set(['web_enable', 'web_search', 'source_check', 'fetch_content', 'get_search_content']);

export function checkCall(name, input, cwd, config) {
  if (name === 'read') {
    try {
      const path = realpathSync(resolve(cwd, input.path));
      if (!config.files.includes(path)) return 'Read only listed source files and research reports.';
    } catch {
      return 'This file is not available in the research file list.';
    }
    return null;
  }
  if (name === 'subagents_enable') return null;
  if (name === 'subagent' && input.action === 'doctor') return null;
  if (!WEB.has(name)) return `Tool ${name} is not permitted in research sessions.`;
  if (name === 'web_search' || name === 'source_check') {
    // Search text still needs judgment. Reject obvious code, paths and large payloads.
    const queries = [input.query, input.claim, ...(input.queries ?? [])].filter(Boolean);
    if (queries.some(q => typeof q !== 'string' || q.length > 400 || /[\n\r{};]|\/home\/|file:|api[_-]?key|bearer\s/i.test(q))) {
      return 'Use a short generic technology query, not code, paths or private data.';
    }
    input.provider = 'openai';
    delete input.model;
    delete input.proxy;
  }
  if (name === 'fetch_content') {
    const urls = [input.url, ...(input.urls ?? [])].filter(Boolean);
    if (!urls.length) return 'Provide a public HTTPS documentation URL.';
    for (const value of urls) {
      let url;
      try { url = new URL(value); } catch { return 'Invalid public HTTPS URL.'; }
      const host = url.hostname.toLowerCase();
      if (url.protocol !== 'https:' || url.username || url.password || url.port ||
          host === 'localhost' || host.endsWith('.local') || host.endsWith('.internal') ||
          !/[a-z]/.test(host) || host.includes(':') || !host.includes('.') ||
          /^(?:\d+\.)/.test(host) || host.endsWith('youtube.com') || host === 'youtu.be') {
        return 'Use public HTTPS text sources, not local services, credentials or video-model tools.';
      }
    }
    if (input.auth || input.forceClone || input.mode === 'answer' || input.model || input.answerModel) {
      return 'Only unauthenticated text retrieval is allowed.';
    }
    input.mode = 'readable';
    input.redirects = 'same-origin';
    delete input.proxy;
  }
  return null;
}

export default function (pi) {
  const config = JSON.parse(readFileSync(process.env.LISTR_RESEARCH_GUARD, 'utf8'));
  let doctorReady = false;
  const matches = ctx => `${ctx.model?.provider}/${ctx.model?.id}` === config.model &&
    ctx.thinkingLevel === config.thinking;
  pi.on('session_start', (_event, ctx) => {
    if (!matches(ctx)) throw new Error('Research model/reasoning mismatch.');
    writeFileSync(config.receipt, JSON.stringify({ model: config.model, thinking: config.thinking }), { mode: 0o600 });
  });
  pi.on('tool_result', event => {
    if (event.toolName === 'subagent' && event.input.action === 'doctor' && !event.isError) {
      const text = event.content.filter(part => part.type === 'text').map(part => part.text).join('\n');
      if (text.includes('Subagents doctor report') && text.includes('async support: available') &&
          text.includes('temp root: ok') && text.includes('async runs: ok')) {
        doctorReady = true;
        writeFileSync(config.doctorReceipt, text, { mode: 0o600 });
      }
    }
  });
  pi.on('tool_call', (event, ctx) => {
    const reason = !matches(ctx) ? 'Research model/reasoning mismatch.' :
      event.toolName === 'read' && !doctorReady ? 'Call subagent action=doctor successfully before source reads.' :
      checkCall(event.toolName, event.input, ctx.cwd, config);
    if (reason) return { block: true, reason };
  });
}
