#!/usr/bin/env node
'use strict';

const fs = require('node:fs/promises');
const path = require('node:path');

const DEFAULT_PLAYWRIGHT_MODULE = '/home/hsa/projects/list_app/.venv/lib/python3.13/site-packages/playwright/driver/package';
const DRAFTS = [
  { id: 'reference', name: 'Current reference', level: 0 },
  { id: 'porcelain-ink', name: 'Porcelain Ink', level: 1 },
  { id: 'citrus-grove', name: 'Citrus Grove', level: 1 },
  { id: 'marine-signal', name: 'Marine Signal', level: 1 },
  { id: 'aubergine', name: 'Aubergine', level: 1 },
  { id: 'ember-clay', name: 'Ember Clay', level: 1 },
  { id: 'market', name: 'Market', level: 2 },
  { id: 'editorial', name: 'Editorial', level: 2 },
  { id: 'utility', name: 'Utility', level: 2 },
  { id: 'cushion', name: 'Cushion', level: 2 },
  { id: 'ledger', name: 'Ledger', level: 2 },
  { id: 'index-rail', name: 'Index Rail', level: 3 },
  { id: 'category-atlas', name: 'Category Atlas', level: 3 },
  { id: 'today-ledger', name: 'Today Ledger', level: 3 },
  { id: 'split-sheet', name: 'Split Sheet', level: 3 },
  { id: 'card-mosaic', name: 'Card Mosaic', level: 3 },
  { id: 'field-notes', name: 'Field Notes', level: 4 },
  { id: 'dispatch-board', name: 'Dispatch Board', level: 4 },
  { id: 'focus-deck', name: 'Focus Deck', level: 4 },
  { id: 'terminal', name: 'Terminal', level: 4 },
  { id: 'orbit-map', name: 'Orbit Map', level: 4 },
];
const MODES = ['light', 'dark'];
const VIEWS = ['room', 'list'];
const VIEWPORTS = [
  { name: 'phone', width: 390, height: 844 },
  { name: 'desktop', width: 1280, height: 900 },
];
const SAMPLE_TEXT = {
  longName: 'AA batteries for the hallway sensor',
  shortName: 'Dish soap',
  checkedName: 'Coffee filters',
  uncheckedName: 'Ripe bananas',
  tags: ['Produce', 'Chilled'],
};

function parseArgs(argv) {
  let baseURL = process.env.BASE_URL || 'http://127.0.0.1:8766/';
  let evidenceDir = process.env.EVIDENCE_DIR || path.resolve(process.cwd(), 'theme-gallery-evidence');
  const positional = [];
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--base-url' && argv[index + 1]) baseURL = argv[++index];
    else if (arg.startsWith('--base-url=')) baseURL = arg.slice('--base-url='.length);
    else if ((arg === '--evidence-dir' || arg === '--evidence-directory') && argv[index + 1]) evidenceDir = argv[++index];
    else if (arg.startsWith('--evidence-dir=')) evidenceDir = arg.slice('--evidence-dir='.length);
    else if (arg === '--help' || arg === '-h') return { help: true };
    else if (arg.startsWith('-')) throw new Error(`Unknown option: ${arg}`);
    else positional.push(arg);
  }
  if (positional[0]) baseURL = positional[0];
  if (positional[1]) evidenceDir = positional[1];
  if (positional.length > 2) throw new Error('Use at most two positional arguments: baseURL evidence-directory');
  return { baseURL, evidenceDir: path.resolve(evidenceDir) };
}

function helpText() {
  return [
    'Usage: node prototypes/theme-gallery-check.cjs [baseURL] [evidence-directory]',
    '   or: node prototypes/theme-gallery-check.cjs --base-url URL --evidence-dir DIR',
    `Defaults: http://127.0.0.1:8766/ and ${path.resolve(process.cwd(), 'theme-gallery-evidence')}`,
    `Playwright module: PLAYWRIGHT_MODULE or ${DEFAULT_PLAYWRIGHT_MODULE}`,
  ].join('\n');
}

function initializeReport(config) {
  return {
    harness: 'theme-gallery-check.cjs',
    startedAt: new Date().toISOString(),
    baseURL: config.baseURL,
    evidenceDirectory: config.evidenceDir,
    status: 'running',
    expected: {
      drafts: DRAFTS,
      modes: MODES,
      views: VIEWS,
      viewports: VIEWPORTS,
      engines: ['chromium', 'webkit'],
      fullMatrixRuns: DRAFTS.length * MODES.length * VIEWS.length * VIEWPORTS.length * 2,
    },
    methodology: [
      'Use the gallery shell and embedded preview DOM; no app source, API, account, or production data is used.',
      'Exercise every draft including the separate reference in both modes, both views, both viewport sizes, and Chromium and WebKit.',
      'Compare Level 1 reference-screen geometry and selected computed non-color layout, spacing, sizing, and typography properties for each matching engine/mode/view/viewport.',
      'Run keyboard add, check/uncheck, and edit flows for every preview in both engines; test gallery focus and 2-, 3-, and 4-draft comparisons.',
      'Monitor browser requests for cross-origin network activity and failed or HTTP-error assets.',
      'Capture focused 390px and 1280px Chromium screenshots for each draft and build local HTML/PNG contact sheets.',
    ],
    limitations: [
      'Contrast is a practical DOM sample, not a full WCAG audit. It composites parsed solid ancestor background colors and uses 4.5:1 for ordinary text and 3:1 for large text.',
      'Text over CSS images/gradients or unsupported color syntax is recorded as unverified. Pseudo-elements, canvas/SVG-internal text, shadows, blend modes, complex ancestor opacity, antialiasing, and transient states can produce false positives or missed issues.',
      'Focus styling is sampled after programmatic focus; keyboard add/check/edit flows verify real keyboard activation, but this is not a screen-reader or full keyboard-only usability audit.',
      'The phone overflow check is conservative: absolutely positioned or decorative children outside the preview box can be flagged even when they are not user-scrollable; inspect the listed offender details.',
      'Touch-target warnings use a 24px minimum and note targets below 44px. The measurement does not judge spacing between adjacent targets or context-specific exceptions.',
      'Screenshots and contact sheets are representative Chromium captures. WebKit is exercised for behavior and computed checks but does not produce duplicate screenshots.'
    ],
    checks: [],
    failures: [],
    externalRequests: [],
    pageErrors: [],
    consoleErrors: [],
    screenshots: [],
    matrixRuns: 0,
    interactionRuns: 0,
  };
}

function record(report, id, status, details = {}) {
  const item = { id, status, ...details };
  report.checks.push(item);
  if (status === 'failed') report.failures.push(item);
  return item;
}

function formatError(error) {
  return error && error.stack ? error.stack : String(error);
}

function localDocumentURL(baseURL) {
  const url = new URL(baseURL);
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error(`baseURL must be an HTTP(S) loopback URL; got ${url.protocol}`);
  const loopback = ['localhost', '127.0.0.1', '::1'].includes(url.hostname.replace(/^\[|\]$/g, ''));
  if (!loopback) throw new Error(`Refusing non-loopback baseURL ${url.origin}; this harness is for a local gallery only.`);
  url.search = '';
  url.hash = '';
  if (url.pathname.endsWith('/preview.html')) return url;
  if (url.pathname.endsWith('/index.html')) {
    url.pathname = `${url.pathname.slice(0, -'index.html'.length)}preview.html`;
  } else if (url.pathname.endsWith('.html')) {
    url.pathname = `${url.pathname.slice(0, url.pathname.lastIndexOf('/') + 1)}preview.html`;
  } else {
    if (!url.pathname.endsWith('/')) url.pathname += '/';
    url.pathname += 'preview.html';
  }
  return url;
}

function previewURL(documentURL, draft, mode, view) {
  const url = new URL(documentURL.href);
  url.search = '';
  url.hash = '';
  url.searchParams.set('draft', draft);
  url.searchParams.set('mode', mode);
  url.searchParams.set('view', view);
  return url.href;
}

function previewSelector(id) {
  return `#viewer .prototype[data-draft-id="${id}"]`;
}

async function openPreview(page, documentURL, draft, mode, view, viewport) {
  await page.setViewportSize({ width: viewport.width, height: viewport.height });
  await page.goto(previewURL(documentURL, draft.id, mode, view), { waitUntil: 'domcontentloaded' });
  const root = page.locator(previewSelector(draft.id));
  await root.waitFor({ state: 'visible' });
  return root;
}

async function checkOverview(page, documentURL, report) {
  await page.goto(documentURL.href, { waitUntil: 'domcontentloaded' });
  await page.locator('#draft-groups').waitFor({ state: 'visible' });
  const cardCounts = await page.locator('#draft-groups [data-card-id]').count();
  record(report, 'gallery-overview-count', cardCounts === DRAFTS.length ? 'passed' : 'failed', {
    expected: DRAFTS.length,
    actual: cardCounts,
  });
  for (let level = 1; level <= 4; level += 1) {
    const actual = await page.locator('#draft-groups .level-group').nth(level - 1).locator('[data-card-id]').count();
    record(report, `gallery-level-${level}-count`, actual === 5 ? 'passed' : 'failed', { expected: 5, actual });
  }
  const reference = page.locator('#draft-groups .reference-group [data-card-id="reference"]');
  const referenceCount = await reference.count();
  record(report, 'gallery-separate-reference', referenceCount === 1 ? 'passed' : 'failed', { expected: 1, actual: referenceCount });
  return cardCounts === DRAFTS.length;
}

async function testGalleryKeyboardFlow(page, documentURL, report) {
  for (const count of [2, 3, 4]) {
    await page.goto(documentURL.href, { waitUntil: 'domcontentloaded' });
    for (const draft of DRAFTS.filter((item) => item.level > 0).slice(0, count)) {
      const checkbox = page.locator(`#draft-groups input[data-action="select-draft"][value="${draft.id}"]`);
      await checkbox.focus();
      await page.keyboard.press('Space');
    }
    const selected = await page.locator('#draft-groups input[data-action="select-draft"]:checked').count();
    const compare = page.locator('#compare-button');
    const enabled = await compare.isEnabled();
    if (enabled) {
      await compare.focus();
      await page.keyboard.press('Enter');
      const shown = await page.locator('#viewer .prototype[data-draft-id]').count();
      const columnTops = await page.locator('#viewer .preview-column').evaluateAll((columns) => columns.map((el) => el.getBoundingClientRect().top));
      const sameRow = columnTops.length === count && Math.max(...columnTops) - Math.min(...columnTops) < 1;
      const url = new URL(page.url());
      const actualCompareCount = (url.searchParams.get('compare') || '').split(',').filter(Boolean).length;
      record(report, `gallery-compare-${count}`, selected === count && shown === count && actualCompareCount === count && sameRow ? 'passed' : 'failed', {
        selected,
        previews: shown,
        routeCompareCount: actualCompareCount,
        sideBySide: sameRow,
      });
    } else {
      record(report, `gallery-compare-${count}`, 'failed', { selected, compareEnabled: enabled });
    }
  }

  await page.goto(documentURL.href, { waitUntil: 'domcontentloaded' });
  for (const draft of DRAFTS.filter((item) => item.level > 0).slice(0, 5)) {
    const checkbox = page.locator(`#draft-groups input[data-action="select-draft"][value="${draft.id}"]`);
    await checkbox.focus();
    await page.keyboard.press('Space');
  }
  const selectedAtLimit = await page.locator('#draft-groups input[data-action="select-draft"]:checked').count();
  record(report, 'gallery-compare-maximum-four', selectedAtLimit === 4 ? 'passed' : 'failed', { expected: 4, actual: selectedAtLimit });

  for (const draft of DRAFTS) {
    await page.goto(documentURL.href, { waitUntil: 'domcontentloaded' });
    const openButton = page.locator(`#draft-groups [data-card-id="${draft.id}"] button[data-action="open-draft"]`);
    const openCount = await openButton.count();
    if (openCount !== 1) {
      record(report, `gallery-focus-${draft.id}`, 'failed', { expectedOpenButton: 1, actual: openCount });
      continue;
    }
    await openButton.focus();
    await page.keyboard.press('Enter');
    const root = page.locator(previewSelector(draft.id));
    const opened = await root.count();
    let roomOK = false;
    let listOK = false;
    let modeOK = false;
    if (opened === 1) {
      const roomButton = page.locator('#viewer [data-action="set-view"][data-view="room"]');
      await roomButton.focus();
      await page.keyboard.press('Enter');
      roomOK = (await root.getAttribute('data-view')) === 'room';
      const listButton = page.locator('#viewer [data-action="set-view"][data-view="list"]');
      await listButton.focus();
      await page.keyboard.press('Enter');
      listOK = (await root.getAttribute('data-view')) === 'list';
      await page.locator('#mode-select').selectOption('dark');
      modeOK = (await page.locator(previewSelector(draft.id)).getAttribute('data-mode')) === 'dark';
      const close = page.locator('#viewer [data-action="close-viewer"]');
      await close.focus();
      await page.keyboard.press('Enter');
    }
    record(report, `gallery-focus-${draft.id}`, opened === 1 && roomOK && listOK && modeOK ? 'passed' : 'failed', {
      openButtons: openCount,
      openedPreviewCount: opened,
      roomSwitch: roomOK,
      listSwitch: listOK,
      modeSwitch: modeOK,
    });
  }
}

function geometryDifference(reference, candidate) {
  const ref = new Map(reference.map((item) => [item.path, item]));
  const next = new Map(candidate.map((item) => [item.path, item]));
  const differences = [];
  for (const [key, left] of ref) {
    const right = next.get(key);
    if (!right) {
      differences.push({ path: key, kind: 'missing-in-draft' });
      continue;
    }
    if (left.tag !== right.tag) differences.push({ path: key, property: 'tag', reference: left.tag, draft: right.tag });
    for (const [property, value] of Object.entries(left.rect)) {
      if (value !== right.rect[property]) differences.push({ path: key, property: `rect.${property}`, reference: value, draft: right.rect[property] });
    }
    for (const [property, value] of Object.entries(left.style)) {
      if (value !== right.style[property]) differences.push({ path: key, property, reference: value, draft: right.style[property] });
    }
    if (differences.length >= 40) break;
  }
  for (const key of next.keys()) {
    if (!ref.has(key)) differences.push({ path: key, kind: 'extra-in-draft' });
    if (differences.length >= 40) break;
  }
  return differences;
}

async function geometrySnapshot(page, draftID) {
  return page.evaluate((id) => {
    const preview = document.querySelector(`#viewer .prototype[data-draft-id="${id}"]`);
    const target = preview?.querySelector('.ref-screen');
    if (!target) return null;
    const properties = [
      'display', 'position', 'top', 'right', 'bottom', 'left', 'box-sizing',
      'width', 'height', 'min-width', 'min-height', 'max-width', 'max-height',
      'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
      'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
      'font-family', 'font-size', 'font-style', 'font-weight', 'font-stretch',
      'font-variant', 'line-height', 'letter-spacing', 'word-spacing', 'text-align',
      'text-transform', 'text-indent', 'text-decoration-line', 'text-decoration-style',
      'text-decoration-thickness', 'white-space', 'overflow-wrap', 'word-break', 'hyphens',
      'gap', 'row-gap', 'column-gap', 'flex-direction', 'flex-wrap', 'flex-grow',
      'flex-shrink', 'flex-basis', 'align-items', 'align-content', 'align-self',
      'justify-content', 'justify-items', 'justify-self', 'order', 'grid-template-columns',
      'grid-template-rows', 'grid-auto-flow', 'grid-auto-columns', 'grid-auto-rows',
      'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
      'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
      'border-top-left-radius', 'border-top-right-radius', 'border-bottom-right-radius',
      'border-bottom-left-radius', 'outline-width', 'outline-style', 'outline-offset',
      'vertical-align', 'overflow-x', 'overflow-y', 'aspect-ratio', 'object-fit',
    ];
    const round = (value) => Math.round(value * 10) / 10;
    const result = [];
    const origin = target.getBoundingClientRect();
    const nodes = [target, ...target.querySelectorAll('*')];
    for (const node of nodes) {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      if (style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 && rect.height === 0) continue;
      let path = 'root';
      if (node !== target) {
        const parts = [];
        let current = node;
        while (current && current !== target) {
          let sameTagIndex = 1;
          for (let sibling = current.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
            if (sibling.tagName === current.tagName) sameTagIndex += 1;
          }
          parts.unshift(`${current.tagName.toLowerCase()}:nth-of-type(${sameTagIndex})`);
          current = current.parentElement;
        }
        path = parts.join(' > ');
      }
      const computed = {};
      for (const property of properties) computed[property] = style.getPropertyValue(property).trim();
      result.push({
        path,
        tag: node.tagName.toLowerCase(),
        rect: { x: round(rect.x - origin.x), y: round(rect.y - origin.y), width: round(rect.width), height: round(rect.height) },
        style: computed,
      });
    }
    return result;
  }, draftID);
}

async function auditContrast(page, draftID) {
  return page.evaluate((id) => {
    const root = document.querySelector(`#viewer .prototype[data-draft-id="${id}"]`);
    if (!root) return { error: 'preview not found' };
    function parseColor(value) {
      if (!value || value === 'transparent') return [0, 0, 0, 0];
      const rgb = value.match(/^rgba?\((.*)\)$/i);
      if (rgb) {
        const parts = rgb[1].replace(/,/g, ' ').replace(/\//g, ' / ').trim().split(/\s+/);
        const slash = parts.indexOf('/');
        const channels = (slash >= 0 ? parts.slice(0, slash) : parts).filter((part) => part !== '/').slice(0, 3);
        let alphaPart = slash >= 0 ? parts[slash + 1] : (parts.length > 3 ? parts[3] : '1');
        const channel = (part) => part.endsWith('%') ? Number.parseFloat(part) * 2.55 : Number.parseFloat(part);
        const alpha = String(alphaPart).endsWith('%') ? Number.parseFloat(alphaPart) / 100 : Number.parseFloat(alphaPart);
        const parsed = [...channels.map(channel), Number.isFinite(alpha) ? alpha : 1];
        return parsed.length === 4 && parsed.every(Number.isFinite) ? parsed : null;
      }
      const hex = value.match(/^#([0-9a-f]{3,8})$/i);
      if (hex) {
        let data = hex[1];
        if (data.length === 3 || data.length === 4) data = [...data].map((character) => character + character).join('');
        if (data.length === 6) data += 'ff';
        if (data.length !== 8) return null;
        return [0, 2, 4].map((index) => Number.parseInt(data.slice(index, index + 2), 16)).concat(Number.parseInt(data.slice(6, 8), 16) / 255);
      }
      // WebKit can retain color(srgb ...) for color-mix(). Normalize with
      // the engine's own color parser, then inspect the resulting sRGB pixel.
      if (CSS.supports('color', value)) {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 1;
        const context = canvas.getContext('2d', { willReadFrequently: true });
        context.clearRect(0, 0, 1, 1);
        context.fillStyle = value;
        context.fillRect(0, 0, 1, 1);
        const pixel = context.getImageData(0, 0, 1, 1).data;
        return [pixel[0], pixel[1], pixel[2], pixel[3] / 255];
      }
      return null;
    }
    function blend(foreground, background) {
      const alpha = foreground[3];
      return [0, 1, 2].map((index) => foreground[index] * alpha + background[index] * (1 - alpha));
    }
    function luminance(color) {
      const channels = color.map((value) => {
        const normalized = value / 255;
        return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    }
    function ratio(left, right) {
      const values = [luminance(left), luminance(right)].sort((a, b) => b - a);
      return (values[0] + 0.05) / (values[1] + 0.05);
    }
    function visible(element) {
      for (let current = element; current; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' || Number(style.opacity) === 0 || current.getAttribute('aria-hidden') === 'true') return false;
      }
      return element.getClientRects().length > 0;
    }
    const fallback = document.documentElement.dataset.mode === 'dark' ? [18, 20, 18] : [255, 255, 255];
    const results = [];
    const unverified = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const text = node.nodeValue.replace(/\s+/g, ' ').trim();
      const element = node.parentElement;
      if (!text || !element || !visible(element) || element.closest('svg,script,style,noscript')) continue;
      const style = getComputedStyle(element);
      const chain = [];
      for (let current = element; current; current = current.parentElement) {
        chain.unshift(current);
        if (current === document.documentElement) break;
      }
      const unsupported = [];
      for (const current of chain) {
        const currentStyle = getComputedStyle(current);
        if (currentStyle.backgroundImage !== 'none') unsupported.push('background-image/gradient');
        if (Number(currentStyle.opacity) < 1) unsupported.push('ancestor-opacity');
        if (currentStyle.mixBlendMode !== 'normal' || currentStyle.isolation === 'isolate') unsupported.push('blend/isolation');
      }
      if (unsupported.length) {
        unverified.push({ text: text.slice(0, 72), reasons: [...new Set(unsupported)] });
        continue;
      }
      let background = fallback;
      for (const current of chain) {
        const color = parseColor(getComputedStyle(current).backgroundColor);
        if (!color) {
          unsupported.push('unparsed-background-color');
          break;
        }
        background = blend(color, background);
      }
      const foreground = parseColor(style.color);
      if (!foreground || unsupported.length) {
        unverified.push({ text: text.slice(0, 72), reasons: [...new Set([...unsupported, 'unsupported-color-syntax'])] });
        continue;
      }
      const effectiveForeground = blend(foreground, background);
      const size = Number.parseFloat(style.fontSize) || 16;
      const weight = Number.parseInt(style.fontWeight, 10) || 400;
      const threshold = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
      results.push({
        text: text.slice(0, 72),
        tag: element.tagName.toLowerCase(),
        fontSize: size,
        fontWeight: weight,
        ratio: Math.round(ratio(effectiveForeground, background) * 100) / 100,
        threshold,
      });
    }
    for (const element of root.querySelectorAll('input[placeholder],textarea[placeholder]')) {
      const text = element.placeholder.trim();
      if (!text || !visible(element)) continue;
      const style = getComputedStyle(element, '::placeholder');
      const chain = [];
      for (let current = element; current; current = current.parentElement) {
        chain.unshift(current);
        if (current === document.documentElement) break;
      }
      const unsupported = [];
      let background = fallback;
      for (const current of chain) {
        const currentStyle = getComputedStyle(current);
        if (currentStyle.backgroundImage !== 'none') unsupported.push('background-image/gradient');
        if (Number(currentStyle.opacity) < 1) unsupported.push('ancestor-opacity');
        if (currentStyle.mixBlendMode !== 'normal' || currentStyle.isolation === 'isolate') unsupported.push('blend/isolation');
        const color = parseColor(currentStyle.backgroundColor);
        if (!color) unsupported.push('unparsed-background-color');
        else background = blend(color, background);
      }
      const foreground = parseColor(style.color);
      if (!foreground || unsupported.length) {
        unverified.push({ text: text.slice(0, 72), reasons: [...new Set([...unsupported, 'placeholder-color-unverified'])] });
        continue;
      }
      const effectiveForeground = blend(foreground, background);
      const size = Number.parseFloat(style.fontSize) || 16;
      const weight = Number.parseInt(style.fontWeight, 10) || 400;
      const threshold = size >= 24 || (size >= 18.66 && weight >= 700) ? 3 : 4.5;
      results.push({
        text: text.slice(0, 72),
        tag: `${element.tagName.toLowerCase()}::placeholder`,
        fontSize: size,
        fontWeight: weight,
        ratio: Math.round(ratio(effectiveForeground, background) * 100) / 100,
        threshold,
      });
    }
    const low = results.filter((item) => item.ratio + 0.01 < item.threshold);
    return {
      sampledTextNodes: results.length,
      unverifiedTextNodes: unverified.length,
      minimumRatio: results.length ? Math.min(...results.map((item) => item.ratio)) : null,
      lowContrast: low.slice(0, 15),
      unverifiedExamples: unverified.slice(0, 8),
    };
  }, draftID);
}

async function auditOverflow(page, draftID) {
  return page.evaluate((id) => {
    const root = document.querySelector(`#viewer .prototype[data-draft-id="${id}"]`);
    if (!root) return { error: 'preview not found' };
    const rootRect = root.getBoundingClientRect();
    const overflow = [];
    const intentionalScrollers = [...root.querySelectorAll('[data-intentional-scroll]')].map((el) => ({ purpose: el.dataset.intentionalScroll, width: el.clientWidth, scrollWidth: el.scrollWidth }));
    for (const element of [root, ...root.querySelectorAll('*')]) {
      const style = getComputedStyle(element);
      const scroller = element.closest('[data-intentional-scroll]');
      if (scroller && root.contains(scroller)) {
        const box = scroller.getBoundingClientRect();
        if (box.left >= rootRect.left - 1 && box.right <= rootRect.right + 1 && ['auto', 'scroll'].includes(getComputedStyle(scroller).overflowX)) continue;
      }
      const rect = element.getBoundingClientRect();
      const scrollableX = element.scrollWidth > element.clientWidth + 1 && !['hidden', 'clip'].includes(style.overflowX);
      const escapes = rect.width > 0 && (rect.left < rootRect.left - 1 || rect.right > rootRect.right + 1);
      if (scrollableX || escapes) {
        overflow.push({
          tag: element.tagName.toLowerCase(),
          className: typeof element.className === 'string' ? element.className.slice(0, 100) : '',
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          scrollableX,
          escapesPreview: escapes,
        });
      }
    }
    return {
      viewportWidth: window.innerWidth,
      rootWidth: Math.round(rootRect.width),
      rootScrollWidth: root.scrollWidth,
      rootClientWidth: root.clientWidth,
      rootOverflow: root.scrollWidth > root.clientWidth + 1,
      offenders: overflow.slice(0, 12),
      totalOffenders: overflow.length,
      intentionalScrollers,
    };
  }, draftID);
}

async function auditControls(page, draftID) {
  return page.evaluate((id) => {
    const root = document.querySelector(`#viewer .prototype[data-draft-id="${id}"]`);
    if (!root) return { error: 'preview not found' };
    const selector = 'a[href],button,input,select,textarea,[role="button"],[tabindex]:not([tabindex="-1"])';
    const controls = [...root.querySelectorAll(selector)];
    const missingNames = [];
    const missingFocus = [];
    const smallTargets = [];
    let inspected = 0;
    function normalizedColor(value) {
      const match = value.match(/rgba?\([^)]*\)/i);
      if (!match) return value;
      return match[0].replace(/\s+/g, '').replace(/,1\)$/, ')');
    }
    function accessibleName(element) {
      const aria = element.getAttribute('aria-label');
      if (aria) return aria.trim();
      const labelledby = element.getAttribute('aria-labelledby');
      if (labelledby) {
        const labelText = labelledby.split(/\s+/).map((part) => document.getElementById(part)?.innerText || '').join(' ').trim();
        if (labelText) return labelText;
      }
      if (element.labels?.length) {
        const labelText = [...element.labels].map((label) => label.innerText || '').join(' ').trim();
        if (labelText) return labelText;
      }
      return (element.innerText || element.getAttribute('title') || element.getAttribute('placeholder') || element.value || '').trim();
    }
    function shown(element) {
      for (let current = element; current; current = current.parentElement) {
        const style = getComputedStyle(current);
        if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
      }
      return element.getClientRects().length > 0;
    }
    function focusSignature(element) {
      const style = getComputedStyle(element);
      return {
        outlineStyle: style.outlineStyle,
        outlineWidth: Number.parseFloat(style.outlineWidth) || 0,
        outlineColor: style.outlineColor,
        boxShadow: style.boxShadow,
        borderColor: style.borderColor,
        borderWidth: style.borderWidth,
        backgroundColor: style.backgroundColor,
        color: style.color,
      };
    }
    function hasVisibleOutline(signature) {
      const color = normalizedColor(signature.outlineColor);
      return signature.outlineStyle !== 'none' && signature.outlineWidth > 0 && color !== 'rgba(0,0,0,0)' && color !== 'transparent';
    }
    for (const element of controls) {
      if (!shown(element) || element.disabled || element.getAttribute('aria-disabled') === 'true') continue;
      inspected += 1;
      const name = accessibleName(element);
      const description = {
        tag: element.tagName.toLowerCase(),
        type: element.getAttribute('type') || '',
        name: name.slice(0, 100),
        action: element.getAttribute('data-action') || '',
      };
      if (!name) missingNames.push(description);
      const target = element.matches('input[type="checkbox"],input[type="radio"]') ? (element.closest('label') || element) : element;
      const rect = target.getBoundingClientRect();
      if (rect.width < 24 || rect.height < 24) smallTargets.push({ ...description, width: Math.round(rect.width), height: Math.round(rect.height), belowTouchTarget: rect.width < 44 || rect.height < 44 });
      const before = focusSignature(element);
      try { element.focus({ preventScroll: true }); } catch { /* The control may not support focus. */ }
      const after = focusSignature(element);
      const changed = ['borderColor', 'borderWidth', 'backgroundColor', 'color'].some((key) => before[key] !== after[key]);
      const ring = hasVisibleOutline(after) || (after.boxShadow !== 'none' && after.boxShadow !== before.boxShadow);
      if (!ring && !changed) missingFocus.push(description);
    }
    return {
      inspected,
      missingAccessibleNames: missingNames.slice(0, 12),
      missingFocusIndicators: missingFocus.slice(0, 12),
      below24pxTargets: smallTargets.slice(0, 12),
      below44pxTargets: smallTargets.filter((item) => item.belowTouchTarget).slice(0, 12),
      totalBelow24px: smallTargets.length,
      totalBelow44px: smallTargets.filter((item) => item.belowTouchTarget).length,
    };
  }, draftID);
}

async function checkSampleContent(root, draft, report, viewport, mode) {
  const text = await root.innerText();
  const checks = [
    ['long-name', SAMPLE_TEXT.longName],
    ['short-name', SAMPLE_TEXT.shortName],
    ['checked-item-name', SAMPLE_TEXT.checkedName],
    ['unchecked-item-name', SAMPLE_TEXT.uncheckedName],
    ['tag-produce', SAMPLE_TEXT.tags[0]],
    ['tag-chilled', SAMPLE_TEXT.tags[1]],
  ];
  const missing = checks.filter(([, value]) => !text.includes(value)).map(([name]) => name);
  const row = (id) => root.locator(`[data-item-id="${id}"]:not(button):not(input)`).first();
  const banana = row('bananas');
  const batteries = row('batteries');
  const coffee = row('coffee-filters');
  const bananasCount = await banana.count();
  const batteriesText = await batteries.count() ? await batteries.innerText() : '';
  const bananaText = bananasCount ? await banana.innerText() : '';
  const coffeeChecked = await coffee.locator('input[data-action="check"]').isChecked().catch(() => false);
  const bananaCheckbox = banana.locator('input[data-action="check"]');
  let bananaUnchecked = false;
  try { bananaUnchecked = bananasCount === 1 && !(await bananaCheckbox.isChecked()); } catch { bananaUnchecked = false; }
  const detailsOK = batteriesText.length > 0 && /Nov|Today|Tomorrow|2026/i.test(batteriesText)
    && /Qty\s*6|Quantity\s*6|×\s*6/i.test(bananaText)
    && coffeeChecked
    && bananaUnchecked;
  const status = missing.length === 0 && detailsOK ? 'passed' : 'failed';
  record(report, `sample-content-${draft.id}-${mode}-${viewport.name}`, status, {
    missing,
    dueItemFindable: batteriesText.length > 0 && /Nov|Today|Tomorrow|2026/i.test(batteriesText),
    quantityFindable: /Qty\s*6|Quantity\s*6|×\s*6/i.test(bananaText),
    checkedItemStateFindable: coffeeChecked,
    uncheckedItem: bananaUnchecked,
    view: 'list',
  });
}

async function verifyPreview(page, root, draft, mode, view, viewport, report, engine, referenceGeometry) {
  const observed = {
    draft: await root.getAttribute('data-draft-id'),
    mode: await root.getAttribute('data-mode'),
    view: await root.getAttribute('data-view'),
  };
  const routeOK = observed.draft === draft.id && observed.mode === mode && observed.view === view;
  record(report, `matrix-route-${engine}-${draft.id}-${mode}-${view}-${viewport.width}`, routeOK ? 'passed' : 'failed', { expected: { draft: draft.id, mode, view }, observed });

  if (view === 'list') await checkSampleContent(root, draft, report, viewport, mode);

  const contrast = await auditContrast(page, draft.id);
  const lowContrast = contrast.lowContrast || [];
  record(report, `contrast-${engine}-${draft.id}-${mode}-${view}-${viewport.width}`, contrast.error ? 'failed' : lowContrast.length ? 'failed' : 'passed', {
    sampledTextNodes: contrast.sampledTextNodes || 0,
    unverifiedTextNodes: contrast.unverifiedTextNodes || 0,
    minimumRatio: contrast.minimumRatio,
    lowContrast,
    unverifiedExamples: contrast.unverifiedExamples || [],
  });

  if (viewport.width === 390) {
    const overflow = await auditOverflow(page, draft.id);
    record(report, `phone-overflow-${engine}-${draft.id}-${mode}-${view}`, overflow.error ? 'failed' : overflow.rootOverflow || overflow.totalOffenders ? 'failed' : 'passed', overflow);
    const controls = await auditControls(page, draft.id);
    const badControls = (controls.missingAccessibleNames || []).length + (controls.missingFocusIndicators || []).length + (controls.totalBelow24px || 0);
    record(report, `targets-focus-${engine}-${draft.id}-${mode}-${view}`, controls.error ? 'failed' : badControls ? 'failed' : 'passed', controls);
  }

  if (draft.level > 1) return null;
  return geometrySnapshot(page, draft.id);
}

async function captureFocusedScreenshot(page, draft, viewport, evidenceDir, report) {
  const kind = viewport.name;
  const directory = path.join(evidenceDir, 'screenshots', kind);
  await fs.mkdir(directory, { recursive: true });
  const file = path.join(directory, `${draft.id}.png`);
  try {
    await page.locator('#viewer').screenshot({ path: file, animations: 'disabled' });
    report.screenshots.push({ draft: draft.id, viewport: kind, width: viewport.width, path: path.relative(evidenceDir, file) });
  } catch (error) {
    record(report, `screenshot-${kind}-${draft.id}`, 'failed', { error: formatError(error) });
  }
}

async function makeContactSheet(context, viewport, evidenceDir, report) {
  const ids = DRAFTS.map((draft) => draft.id).filter((id) => report.screenshots.some((shot) => shot.draft === id && shot.viewport === viewport.name));
  if (!ids.length) return;
  const images = [];
  for (const id of ids) {
    const filename = path.join(evidenceDir, 'screenshots', viewport.name, `${id}.png`);
    try {
      const data = await fs.readFile(filename);
      images.push({ id, draft: DRAFTS.find((item) => item.id === id), data: data.toString('base64') });
    } catch (error) {
      record(report, `contact-sheet-input-${viewport.name}-${id}`, 'failed', { error: formatError(error) });
    }
  }
  if (!images.length) return;
  const label = viewport.name === 'phone' ? '390 × 844 focused phone previews' : '1280 × 900 focused desktop previews';
  const cells = images.map(({ id, draft, data }) => `<figure><figcaption>${draft.name} <small>${id}</small></figcaption><img alt="${draft.name} preview" src="data:image/png;base64,${data}"></figure>`).join('');
  const html = `<!doctype html><html lang="en"><meta charset="utf-8"><title>${label} · theme gallery</title><style>*{box-sizing:border-box}body{margin:0;padding:18px;background:#f5f3ed;color:#20231f;font:14px/1.4 system-ui,sans-serif}h1{font-size:22px;margin:0 0 16px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}figure{margin:0;padding:8px;background:#fff;border:1px solid #aaa;break-inside:avoid}figcaption{min-height:38px;font-weight:700}figcaption small{display:block;font:11px ui-monospace,monospace;color:#555}img{display:block;width:100%;height:auto;border:1px solid #ddd}@media(max-width:700px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}</style><h1>${label} · ${images.length} previews</h1><main class="grid">${cells}</main></html>`;
  const htmlPath = path.join(evidenceDir, `${viewport.name}-contact-sheet.html`);
  const pngPath = path.join(evidenceDir, `${viewport.name}-contact-sheet.png`);
  await fs.writeFile(htmlPath, html, 'utf8');
  const page = await context.newPage();
  try {
    await page.setViewportSize({ width: 1600, height: 1100 });
    await page.setContent(html, { waitUntil: 'load' });
    await page.screenshot({ path: pngPath, fullPage: true, animations: 'disabled' });
    report.screenshots.push({ viewport: viewport.name, kind: 'contact-sheet', path: path.relative(evidenceDir, pngPath), html: path.relative(evidenceDir, htmlPath), entries: images.length });
  } catch (error) {
    record(report, `contact-sheet-${viewport.name}`, 'failed', { error: formatError(error) });
  } finally {
    await page.close().catch(() => {});
  }
}

async function runMatrix(browser, browserTypeName, documentURL, evidenceDir, report) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    serviceWorkers: 'block',
  });
  const page = await context.newPage();
  page.setDefaultTimeout(7000);
  const baseOrigin = documentURL.origin;
  context.on('request', (request) => {
    let requestURL;
    try { requestURL = new URL(request.url()); } catch { return; }
    if (['http:', 'https:'].includes(requestURL.protocol) && requestURL.origin !== baseOrigin) {
      report.externalRequests.push({ engine: browserTypeName, url: request.url(), method: request.method() });
    }
  });
  context.on('requestfailed', (request) => {
    record(report, `request-failed-${browserTypeName}`, 'failed', { url: request.url(), error: request.failure()?.errorText || 'unknown failure' });
  });
  page.on('response', (response) => {
    if (response.status() >= 400) record(report, `http-error-${browserTypeName}`, 'failed', { url: response.url(), status: response.status() });
  });
  page.on('pageerror', (error) => report.pageErrors.push({ engine: browserTypeName, message: formatError(error) }));
  page.on('console', (message) => {
    if (message.type() === 'error') report.consoleErrors.push({ engine: browserTypeName, message: message.text() });
  });

  await page.goto(documentURL.href, { waitUntil: 'domcontentloaded' });
  await checkOverview(page, documentURL, report);
  await testGalleryKeyboardFlow(page, documentURL, report);

  for (const viewport of VIEWPORTS) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    for (const mode of MODES) {
      for (const view of VIEWS) {
        let referenceGeometry = null;
        for (const draft of DRAFTS) {
          const root = await openPreview(page, documentURL, draft, mode, view, viewport);
          report.matrixRuns += 1;
          const geometry = await verifyPreview(page, root, draft, mode, view, viewport, report, browserTypeName, referenceGeometry);
          if (draft.level === 0) referenceGeometry = geometry;
          else if (draft.level === 1) {
            const differences = geometry && referenceGeometry ? geometryDifference(referenceGeometry, geometry) : [{ kind: 'missing-reference-snapshot' }];
            record(report, `level1-geometry-${browserTypeName}-${draft.id}-${mode}-${view}-${viewport.width}`, differences.length ? 'failed' : 'passed', {
              differenceCount: differences.length,
              differences: differences.slice(0, 20),
              comparedElementCount: geometry?.length || 0,
              referenceElementCount: referenceGeometry?.length || 0,
            });
          }
          if (browserTypeName === 'chromium' && mode === 'light' && view === 'list' && (viewport.width === 390 || viewport.width === 1280)) {
            await captureFocusedScreenshot(page, draft, viewport, evidenceDir, report);
          }
        }
      }
    }
  }

  for (const mode of MODES) for (const draft of DRAFTS) {
    await openPreview(page, documentURL, draft, mode, 'list', VIEWPORTS[0]);
    const uniqueName = `Harness sample ${draft.id} ${mode}`;
    const rootSelector = previewSelector(draft.id);
    const form = page.locator(`${rootSelector} form[data-action="add"]`);
    const addInput = form.locator('input[name="item"]');
    const addButton = form.locator('button[type="submit"]');
    const addAvailable = await form.count() === 1 && await addInput.count() === 1 && await addButton.count() === 1;
    let addWorked = false;
    if (addAvailable) {
      await addInput.focus();
      await addInput.pressSequentially(uniqueName);
      await addInput.press('Enter');
      addWorked = (await page.locator(rootSelector).innerText()).includes(uniqueName);
    }
    const addFocus = await addInput.evaluate((el) => document.activeElement === el).catch(() => false);
    record(report, `keyboard-add-${browserTypeName}-${draft.id}-${mode}`, addAvailable && addWorked && addFocus ? 'passed' : 'failed', { formAvailable: addAvailable, addedTextVisible: addWorked, focusRetainedInPreview: addFocus });

    const unchecked = page.locator(`${rootSelector} input[data-action="check"][data-item-id="bananas"]`);
    let checkWorked = false;
    let uncheckWorked = false;
    let checkFocus = false;
    if (await unchecked.count() === 1) {
      await unchecked.focus();
      await unchecked.press('Space');
      const checkedAgain = page.locator(`${rootSelector} input[data-action="check"][data-item-id="bananas"]`);
      checkWorked = await checkedAgain.isChecked();
      checkFocus = await checkedAgain.evaluate((el) => document.activeElement === el);
      await checkedAgain.focus();
      await checkedAgain.press('Space');
      const uncheckedAgain = page.locator(`${rootSelector} input[data-action="check"][data-item-id="bananas"]`);
      uncheckWorked = !(await uncheckedAgain.isChecked());
    }
    record(report, `keyboard-check-uncheck-${browserTypeName}-${draft.id}-${mode}`, checkWorked && uncheckWorked && checkFocus ? 'passed' : 'failed', { checkWorked, uncheckWorked, focusRetainedInPreview: checkFocus });

    const editButton = page.locator(`${rootSelector} [data-action="edit"][data-item-id="bananas"]`).first();
    const editAvailable = await editButton.count() === 1;
    let editOpened = false;
    let editSaved = false;
    if (editAvailable) {
      await editButton.focus();
      await editButton.press('Enter');
      const dialog = page.locator('#edit-dialog');
      editOpened = await dialog.evaluate((element) => element.open).catch(() => false);
      if (editOpened) {
        const editName = page.locator('#edit-name');
        await editName.focus();
        await editName.press('Control+A');
        await editName.pressSequentially(`Edited ${draft.id}`);
        const save = page.locator('#edit-form button[type="submit"]');
        await save.focus();
        await save.press('Enter');
        const changed = await page.locator('#viewer').innerText().catch(() => '');
        const stillOpen = await dialog.evaluate((element) => element.open).catch(() => false);
        editSaved = changed.includes(`Edited ${draft.id}`) && !stillOpen;
      }
    }
    record(report, `keyboard-edit-${browserTypeName}-${draft.id}-${mode}`, editAvailable && editOpened && editSaved ? 'passed' : 'failed', {
      editButtonAvailable: editAvailable,
      dialogOpenedByEnter: editOpened,
      editedNameVisibleAfterSave: editSaved,
    });
    report.interactionRuns += 1;
  }

  // Every direction must also expose all three non-default sample lists.
  const secondaryLists = [
    { id: 'cabin', items: ['kindling', 'coffee-beans', 'sheets', 'lantern'], tags: ['Cabin', 'Outdoor', 'Pantry'] },
    { id: 'garden', items: ['compost', 'twine', 'gloves'], tags: ['Garden', 'Tools'] },
    { id: 'first-aid', items: ['bandages', 'saline', 'pain-relief'], tags: ['Health'] },
  ];
  for (const mode of MODES) for (const draft of DRAFTS) {
    await openPreview(page, documentURL, draft, mode, 'list', VIEWPORTS[0]);
    if (draft.id === 'today-ledger') {
      const headings = await page.locator(`${previewSelector(draft.id)} .timeline-group h3`).allTextContents();
      record(report, `date-order-${browserTypeName}-${mode}`, /Nov 4/.test(headings[0] || '') && headings.at(-1) === 'No date' ? 'passed' : 'failed', { headings });
    }
    for (const list of secondaryLists) {
      await page.getByRole('combobox', { name: 'Choose a sample list', exact: true }).selectOption(list.id);
      const preview = page.locator(previewSelector(draft.id));
      const missingItems = [];
      for (const item of list.items) if (await preview.locator(`input[data-action="check"][data-item-id="${item}"]`).count() !== 1) missingItems.push(item);
      let tagsCorrect = true;
      if (draft.id === 'index-rail') {
        const tags = await preview.locator('.rail-tagline .tag').allTextContents();
        tagsCorrect = JSON.stringify([...tags].sort()) === JSON.stringify([...list.tags].sort());
      }
      record(report, `secondary-list-${browserTypeName}-${draft.id}-${mode}-${list.id}`, !missingItems.length && tagsCorrect ? 'passed' : 'failed', { missingItems, tagsCorrect });
      report.secondaryListRuns = (report.secondaryListRuns || 0) + 1;
    }
  }

  // A second comparison column must retain keyboard focus after shared updates.
  const comparisonURL = new URL(documentURL.href);
  comparisonURL.search = '?compare=porcelain-ink,card-mosaic&mode=dark&view=list';
  await page.goto(comparisonURL.href, { waitUntil: 'domcontentloaded' });
  const second = page.locator(previewSelector('card-mosaic'));
  await second.waitFor({ state: 'visible' });
  const comparisonInput = second.locator('form[data-action="add"] input[name="item"]');
  await comparisonInput.fill('Comparison focus sample');
  await comparisonInput.press('Enter');
  const comparisonAddFocus = await comparisonInput.evaluate((el) => document.activeElement === el);
  const comparisonCheck = second.locator('input[data-action="check"][data-item-id="bananas"]');
  await comparisonCheck.focus();
  await comparisonCheck.press('Space');
  const comparisonCheckFocus = await comparisonCheck.evaluate((el) => document.activeElement === el);
  const duplicateIDs = await page.locator('#viewer').evaluate((viewer) => {
    const ids = [...viewer.querySelectorAll('[id]')].map((el) => el.id);
    return ids.filter((id, index) => ids.indexOf(id) !== index);
  });
  record(report, `comparison-focus-${browserTypeName}`, comparisonAddFocus && comparisonCheckFocus && !duplicateIDs.length ? 'passed' : 'failed', { comparisonAddFocus, comparisonCheckFocus, duplicateIDs });

  for (const request of report.externalRequests.filter((item) => item.engine === browserTypeName)) {
    record(report, `no-remote-request-${browserTypeName}`, 'failed', { url: request.url, method: request.method });
  }
  for (const error of report.pageErrors.filter((item) => item.engine === browserTypeName)) {
    record(report, `page-runtime-error-${browserTypeName}`, 'failed', { message: error.message });
  }
  for (const error of report.consoleErrors.filter((item) => item.engine === browserTypeName)) {
    record(report, `console-error-${browserTypeName}`, 'failed', { message: error.message });
  }

  if (browserTypeName === 'chromium') {
    for (const viewport of VIEWPORTS) await makeContactSheet(context, viewport, evidenceDir, report);
  }
  await context.close();
}

async function writeReport(report, evidenceDir) {
  report.finishedAt = new Date().toISOString();
  report.failureCount = report.failures.length;
  report.status = report.failureCount ? 'failed' : 'passed';
  report.externalRequestCount = report.externalRequests.length;
  report.pageErrorCount = report.pageErrors.length;
  report.consoleErrorCount = report.consoleErrors.length;
  await fs.mkdir(evidenceDir, { recursive: true });
  const filename = path.join(evidenceDir, 'evidence.json');
  await fs.writeFile(filename, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  return filename;
}

async function main() {
  let config;
  try {
    config = parseArgs(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(`${error.message}\n${helpText()}\n`);
    process.exitCode = 2;
    return;
  }
  if (config.help) {
    process.stdout.write(`${helpText()}\n`);
    return;
  }

  const report = initializeReport(config);
  let reportPath;
  try {
    await fs.mkdir(config.evidenceDir, { recursive: true });
    const documentURL = localDocumentURL(config.baseURL);
    let playwright;
    const modulePath = process.env.PLAYWRIGHT_MODULE || DEFAULT_PLAYWRIGHT_MODULE;
    try {
      playwright = require(modulePath);
    } catch (error) {
      record(report, 'load-playwright', 'failed', { module: modulePath, error: formatError(error) });
    }
    for (const engine of playwright ? ['chromium', 'webkit'] : []) {
      const browserType = playwright[engine];
      if (!browserType || typeof browserType.launch !== 'function') {
        record(report, `engine-available-${engine}`, 'failed', { message: `Playwright module does not expose ${engine}.` });
        continue;
      }
      let browser;
      try {
        browser = await browserType.launch({ headless: true });
      } catch (error) {
        record(report, `engine-launch-${engine}`, 'failed', { error: formatError(error) });
        continue;
      }
      try {
        await runMatrix(browser, engine, documentURL, config.evidenceDir, report);
      } catch (error) {
        record(report, `engine-run-${engine}`, 'failed', { error: formatError(error) });
      } finally {
        await browser.close().catch((error) => record(report, `engine-close-${engine}`, 'failed', { error: formatError(error) }));
      }
    }
  } catch (error) {
    record(report, 'harness-runtime', 'failed', { error: formatError(error) });
  } finally {
    try {
      reportPath = await writeReport(report, config.evidenceDir);
      process.stdout.write(`Evidence: ${reportPath}\nStatus: ${report.status} (${report.failures.length} failures, ${report.checks.length} checks)\n`);
    } catch (error) {
      process.stderr.write(`Could not preserve evidence in ${config.evidenceDir}: ${formatError(error)}\n`);
      process.exitCode = 2;
    }
  }
  if (report.failures.length) process.exitCode = 1;
}

if (require.main === module) main();

module.exports = {
  DRAFTS,
  VIEWPORTS,
  MODES,
  VIEWS,
  parseArgs,
  geometryDifference,
  localDocumentURL,
  previewURL,
};
