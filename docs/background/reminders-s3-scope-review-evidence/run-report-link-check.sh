#!/usr/bin/env bash
set -eu
cd /home/hsa/projects/list_app-night-s3-review
# Render only to memory. No site publication, server, network or source change.
PYTHONPATH="$PWD/scripts" UV_PROJECT_ENVIRONMENT=/home/hsa/projects/list_app/.venv uv run --offline --no-sync python - <<'PY'
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown
from build_docs_site import PageLinks

root = Path.cwd().resolve()
evidence = root / 'docs/background/reminders-s3-scope-review-evidence'
sources = [root / 'docs/background/reminders-s3-scope-review.md']
sources += [evidence / name for name in ('ownership.md', 'research-checks.md', 'scout-disposition.md', 'closeout.md') if (evidence / name).exists()]
rendered = {}
def page(path):
    if path not in rendered:
        html = markdown.markdown(path.read_text(), extensions=['tables', 'fenced_code', 'toc'])
        parser = PageLinks()
        parser.feed(html)
        rendered[path] = (html, parser)
    return rendered[path]
checked = []
external = []
failures = []
for source in sources:
    html, parser = page(source)
    for href in parser.hrefs:
        parts = urlsplit(href)
        if parts.scheme or parts.netloc:
            external.append({'source': str(source.relative_to(root)), 'href': href, 'status': 'not fetched'})
            continue
        target = (source.parent / unquote(parts.path)).resolve() if parts.path else source
        item = {'source': str(source.relative_to(root)), 'href': href, 'target': str(target.relative_to(root)) if target.is_relative_to(root) else str(target)}
        if target.is_relative_to(root) and target.is_dir() and parts.path.endswith('/') and not parts.fragment:
            checked.append({**item, 'kind': 'existing source directory; not a rendered page'})
            continue
        if not target.is_relative_to(root) or not target.is_file():
            failures.append({**item, 'error': 'missing file or path escapes repo'})
            continue
        if parts.fragment:
            if target.suffix != '.md' or unquote(parts.fragment) not in page(target)[1].ids:
                failures.append({**item, 'error': 'missing source Markdown fragment'})
                continue
        checked.append(item)
result = {'root': str(root), 'parser': f'Python Markdown {markdown.__version__}; tables/fenced_code/toc', 'scope': 'authored Task5 Markdown; raw scout/inherited evidence preserved, not rewritten or render-approved; generated main docs checked separately by canonical site wrapper', 'sources': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, 'local_links_checked': len(checked), 'links': checked, 'external_not_fetched': external, 'failures': failures, 'report_html_tables': page(sources[0])[0].count('<table>'), 'report_html_headings': len(page(sources[0])[1].ids)}
(evidence / 'report-source-link-check.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:result[k] for k in ('parser','local_links_checked','report_html_tables','report_html_headings','failures')}, indent=2))
raise SystemExit(bool(failures))
PY
