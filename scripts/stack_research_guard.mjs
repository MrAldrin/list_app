// Explicitly loaded only by stack_research.py. No global Pi configuration changes.
import { appendFileSync, existsSync, readFileSync, realpathSync, writeFileSync } from 'node:fs';
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
  const emit = event => appendFileSync(config.events, JSON.stringify(event) + '\n', { mode: 0o600 });
  let shutdownTimer;
  pi.on('session_start', (_event, ctx) => {
    if (!matches(ctx) || ctx.mode !== 'tui') throw new Error('Research requires the approved model/tier in interactive Pi.');
    emit({ type: 'session', id: ctx.sessionManager.getSessionId(), cwd: ctx.cwd });
    writeFileSync(config.receipt, JSON.stringify({
      model: config.model, thinking: config.thinking, mode: ctx.mode,
      session_id: ctx.sessionManager.getSessionId(), cwd: ctx.cwd,
      pane_id: process.env.ZELLIJ_PANE_ID, zellij_session: process.env.ZELLIJ_SESSION_NAME,
    }), { mode: 0o600 });
    shutdownTimer = setInterval(() => {
      if (existsSync(config.shutdown)) { ctx.abort(); ctx.shutdown(); }
    }, 100);
  });
  pi.on('session_shutdown', () => clearInterval(shutdownTimer));
  pi.on('before_agent_start', async (_event, ctx) => {
    while (!existsSync(config.dispatch)) {
      if (existsSync(config.shutdown) || existsSync(config.stop)) { ctx.abort(); return; }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  });
  pi.on('input', (event, ctx) => {
    if (/^(?:please\s+)?(?:stop|pause|abort|cancel)\b/i.test(event.text.trim())) {
      writeFileSync(config.stop, 'Stopped from the interactive agent pane.\n', { mode: 0o600 });
      ctx.abort();
      return { action: 'handled' };
    }
  });
  pi.on('message_end', event => {
    if (event.message.role === 'assistant') emit({ type: 'message_end', message: event.message });
  });
  pi.on('tool_execution_start', event => emit({ type: 'tool_execution_start', ...event }));
  pi.on('tool_execution_end', event => emit({ type: 'tool_execution_end', ...event }));
  pi.on('agent_settled', event => emit({ type: 'agent_settled', aborted: event.aborted }));
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
