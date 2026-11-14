# Oxlint-first lint review — lr-347.10.15

Date: 2026-11-14. Change: `yzmnnmup`.
Baseline: accepted BA.1, `wyqynull / a71f1eee`.
Workspace: `/home/hsa/projects/list_app-lr-347.10.15`.
This is an unaccepted task change, not a deployment.

## Decision

**Use native Oxlint checks first. Keep ESLint for Svelte. Do not drop ESLint.**

Oxlint checks scripts, not Svelte template expressions. Removing every mapped
ESLint rule from `.svelte` files would lose checks. A negative test proves this:
Oxlint accepts `(value?.items).join(",")` in a template, while the retained
ESLint `no-unsafe-optional-chaining` rule rejects it.

The implementation moves the 83 mapped rule names to Oxlint for plain scripts.
The effective sets are 79 for JavaScript and 67 for TypeScript, with 83 unique
names. It preserves the previous file-specific settings instead of enabling
the union on every file. The Svelte `no-self-assign` exception also stays.
Only the unsupported, empty `preserve-caught-error.errorClassNames` option is
omitted from the native configuration.

ESLint keeps the 37 configured Svelte rules and two parser-redundant core rules.
It also keeps the previous mapped checks on `.svelte` files, because those checks
can visit template expressions and functions. This repeats some script checks,
but does not trade away template coverage for a smaller timing.

The two approved direct development dependencies are pinned to `1.93.0`:
`oxlint` and `eslint-plugin-oxlint`. The lock adds only their dependency tree;
no existing package entry changes. No other direct dependency is added.
The config-derived exclusions include the explicitly enabled nursery rule
`no-useless-assignment`; the plugin needs `withNursery: true` to disable its
ESLint copy. No additional nursery rules are enabled.

The finding in `src/lib/data/api.test.ts:30` is fixed, not suppressed. The test
now checks the headers object with `toMatchObject`. Missing headers still fail
the test, without indexing a possibly undefined value. Product code is unchanged.

Current commands and configuration ownership are in the
[frontend guide](../../frontend/README.md#checks).

## Measurements

Wall seconds; three runs in each row.

| Command | Every run | Median | Exit |
| --- | --- | ---: | --- |
| Before: npm run lint (Prettier + ESLint) | 10.701, 9.965, 12.423 | 10.701 | All 0 |
| After: npm run lint (Prettier + Oxlint + ESLint) | 9.717, 10.240, 10.019 | 10.019 | All 0 |
| Before: ESLint only | 8.536, 7.634, 7.255 | 7.634 | All 0 |
| After: Oxlint + retained ESLint | 7.034, 7.103, 7.099 | 7.099 | All 0 |
| After: Oxlint only | 0.051, 0.054, 0.053 | 0.053 | All 0 |

Median full lint time falls by 0.682 s (6.4%). The combined lint-engine step
falls by 0.535 s (7.0%). This is a modest total gain, not a 100-fold replacement
of the whole lint gate.

The baseline has 193 script/component inputs. The result has 194, including the
new lint-configuration test file. Node is 24.22.2 and npm is 11.19.1. Both stages
use the same existing locked package versions. Installed tools are ESLint
10.11.0, eslint-plugin-svelte 3.23.0, Svelte 5.57.1, SvelteKit 3.0.0,
svelte-check 4.7.6, TypeScript 6.0.3 and Prettier 3.9.9.

Every timing and full check holds the machine-wide browser lock and the older
project lock, in that order. Lock wait is outside the measurement. Commands are
sequential and use wall time. There is no ESLint result cache. Package download
and install time are excluded. The baseline lint command includes Prettier;
the combined native-plus-ESLint row does not. The latter must be compared with
the ESLint-only baseline, not with the full lint command.

## All 39 unmatched rule names

These are configured rule names, not 39 equally active runtime checks. Version,
runes-mode and parser-service guards can make a configured rule inactive.
No native Oxlint Svelte rule set exists in the tested version.

**Key:** `No` means no equivalent check outside ESLint was established.
`Partial` is not permission to remove the original rule. `Script probe` means
that loading the existing `eslint-plugin-svelte` as an Oxlint JS plugin caught
the supplied script example. It is not full conformance evidence. The adopted
configuration does not enable this alpha JS-plugin route.

| Rule | svelte-check / compiler coverage | Oxlint plugin coverage | Result outside ESLint |
| --- | --- | --- | --- |
| `no-dupe-args` | Module/strict syntax rejects duplicate parameters. | Native module parser rejects the negative fixture. | Covered by parsing. |
| `no-octal` | Module/strict syntax rejects legacy octal literals. | Native module parser rejects the negative fixture. | Covered by parsing. |
| `svelte/comment-directive` | No support for ESLint disable comments in templates. | No template parser. | ESLint support code, not a product bug check. |
| `svelte/infinite-reactive-loop` | Runes mode rejects `$:` itself. Legacy-mode probe has no warning for an async loop. | No Svelte reactive-statement AST. | Legacy-only guard; not an equivalent loop analysis. |
| `svelte/no-at-debug-tags` | `{@debug}` is allowed without a warning. | No template parser. | No. |
| `svelte/no-at-html-tags` | `{@html}` is allowed without a warning; the compiler does not establish safe HTML. | No template parser. | No. |
| `svelte/no-dom-manipulating` | Direct changes to a `bind:this` element pass. | Script-only AST cannot connect the binding to later DOM writes. | No. |
| `svelte/no-dupe-else-if-blocks` | Repeated template conditions pass. | No template parser. | No. |
| `svelte/no-dupe-on-directives` | Deprecation warnings for `on:` are not duplicate-handler checks. | No template parser. | No. |
| `svelte/no-dupe-style-properties` | Repeated inline CSS properties pass. | No template parser. | No. |
| `svelte/no-dupe-use-directives` | Repeated identical actions pass. | No template parser. | No. |
| `svelte/no-export-load-in-svelte-module-in-kit-pages` | A module `load` export passes the isolated component check. A legacy `context` warning does not catch the export. | No Svelte script-element/page context AST. | No. |
| `svelte/no-immutable-reactive-statements` | Runes mode rejects `$:`; legacy immutable-dependency probe passes. | No Svelte reactive-statement AST. | Legacy-only guard; no equivalent dependency check. |
| `svelte/no-inner-declarations` | Compiler/type checks do not replace the Svelte-aware ESLint wrapper. | A native core `no-inner-declarations` exists, not this wrapper. | No verified equivalent. Current ESLint defaults allow block-scoped functions. |
| `svelte/no-inspect` | `$inspect` is allowed without a warning. | Script probes catch it in `.svelte` and `.svelte.ts`. | Partial: promising JS-plugin reuse, not a native check. |
| `svelte/no-navigation-without-resolve` | No `resolve()` requirement from compiler/type checks. | No native equivalent; template links need a template AST. | No. The installed rule's version guard supports Kit 1/2, not this project's Kit 3. |
| `svelte/no-not-function-handler` | Type checking rejects the numeric DOM-handler probe. It is not proof for every custom component or untyped value. | No template parser for handlers. | Partial. |
| `svelte/no-object-in-text-mustaches` | Object text interpolation passes. | No template parser. | No. |
| `svelte/no-raw-special-elements` | The raw `<window>` probe passes. | No template parser. | No. |
| `svelte/no-reactive-functions` | Runes mode rejects `$:`; legacy reactive-function probe passes. | No Svelte reactive-statement AST. | Legacy-only guard; no equivalent policy in legacy mode. |
| `svelte/no-reactive-literals` | Runes mode rejects `$:`; legacy literal assignment passes. | No Svelte reactive-statement AST. | Legacy-only guard; no equivalent policy in legacy mode. |
| `svelte/no-reactive-reassign` | Runes mode rejects `$:`; legacy derived-value reassignment passes. | No Svelte reactive-statement/binding AST. | Legacy-only guard; no equivalent legacy reassignment check. |
| `svelte/no-shorthand-style-property-overrides` | A later shorthand that overwrites a longhand passes. | No template parser. | No. |
| `svelte/no-store-async` | Typed `readable` rejects the async notifier probe. Types are not a blanket source-level ban. | Script probe catches the async notifier. | Partial: type check plus possible JS-plugin reuse. |
| `svelte/no-svelte-internal` | Runes component compiler rejects the static import. This does not cover all plain JS/TS imports, re-exports or dynamic imports. | Script probes catch static imports in `.svelte` and `.ts`. | Partial: compiler plus possible JS-plugin reuse. |
| `svelte/no-unknown-style-directive-property` | Misspelled `style:colro` passes. | No template parser. | No. |
| `svelte/no-unnecessary-state-wrap` | `$state(new SvelteMap())` passes. | Script probe catches the redundant wrap. | Partial: possible JS-plugin reuse. |
| `svelte/no-unused-props` | Unused members in a `$props()` type pass. Legacy unused-export warnings are different. | The Svelte rule needs TypeScript parser services, absent in this JS-plugin path. | No. |
| `svelte/no-unused-svelte-ignore` | An unused, valid warning suppression passes. Invalid-code warnings are a different check. | No template comments or compiler-warning integration. | No. |
| `svelte/no-useless-children-snippet` | Redundant explicit `children` snippet passes. | No template parser. | No. |
| `svelte/no-useless-mustaches` | String-literal interpolation passes. | No template parser. | No. |
| `svelte/prefer-svelte-reactivity` | Mutating a plain `Map` used in the template passes. General state warnings are not this class policy. | Script probe catches a mutated `Map`. | Partial: possible JS-plugin reuse; template references remain unsupported. |
| `svelte/prefer-writable-derived` | The `$state` plus `$effect` assignment probe passes. | Script probe catches the pattern. | Partial: possible JS-plugin reuse. |
| `svelte/require-each-key` | Unkeyed loops are valid Svelte and pass. | No template parser. | No. |
| `svelte/require-event-dispatcher-types` | Missing dispatcher type parameters pass. | No verified replacement for the Svelte/TS wrapper. | Configured rule is gated to Svelte 3/4, so it is inactive on Svelte 5. |
| `svelte/require-store-reactive-access` | Raw store text interpolation passes. Some typed operators can fail for other reasons. | Requires Svelte parser services and template/store context. | No equivalent general check. |
| `svelte/system` | Does not implement ESLint rule/comment coordination. | No equivalent integration. | ESLint support code, not a product bug check. |
| `svelte/valid-each-key` | A constant key passes compile/type checks. Runtime duplicate-key errors do not enforce use of each variables. | No template parser. | No. |
| `svelte/valid-prop-names-in-kit-pages` | An arbitrary route-component prop passes the isolated compiler/type check. SvelteKit checks elsewhere are not a demonstrated substitute. | No Svelte page/props context AST. | No verified equivalent. |

The rows marked **No** are the named checks not covered by another verified
layer. The legacy and version-gated rows are separate: some do not run on the
current app, but keeping their configuration does not cost a new tool. Neither
an inactive rule nor an ESLint support rule is evidence that all template checks
can be removed.

### Evidence and limits

The review reads the installed implementations of all 37 Svelte rules, their
version guards, and compiler diagnostics. It runs 34 component probes against
the installed compiler and an isolated strict svelte-check project. There are
five additional legacy-mode compiler comparisons. The two ESLint integration
rules and the inner-declaration wrapper are source-reviewed rather than claimed
as component probes.

The negative svelte-check project exits 1 with **8 expected errors and 3
warnings**. Five errors reject legacy `$:` in runes mode; the other three are
handler typing, store notifier typing, and the internal import. These are probe
findings, not failures in the maintained app. The isolated check does not run
SvelteKit's full build or establish parity for every typed/legacy form.

An Oxlint JS-plugin trial enables all 37 Svelte rules on the same 34 examples.
Six script checks report their target finding: `no-inspect`, `no-store-async`,
`no-svelte-internal`, `no-unnecessary-state-wrap`, `prefer-svelte-reactivity`
and `prefer-writable-derived`. Template examples, including unsafe raw HTML
and an unkeyed loop, still pass. This confirms the documented custom-parser
gap. There are no plugin crashes or timeout kills in these probes.

These six checks are a possible later reduction of the ESLint rule set, not a
route to remove ESLint now. Enabling the JS bridge would also add about 0.35 s
of observed startup per probe. It would not remove the retained Svelte ESLint
process. No bridge configuration or custom parser is added to the app.

Sources, checked 2026-11-14:

- [Oxlint migration and side-by-side configuration](https://oxc.rs/docs/guide/usage/linter/migrate-from-eslint.html).
- [Framework compatibility: no template linting](https://oxc.rs/compatibility.html).
- [Oxlint JS plugins: custom parsers and type-aware plugin rules are not supported](https://oxc.rs/docs/guide/usage/linter/js-plugins.html).
- [Svelte compiler warnings](https://svelte.dev/docs/svelte/compiler-warnings)
  and [errors](https://svelte.dev/docs/svelte/compiler-errors).
- [Svelte ESLint rule reference](https://sveltejs.github.io/eslint-plugin-svelte/rules/).
  The installed rule source and probe outputs take precedence over a matching
  rule name or a general web compatibility claim.

## Checks and retained work

- Clean `npm ci`: passes. npm still reports the same 15 existing advisories
  (2 low, 11 moderate, 2 high). No audit fix or unrelated upgrade was run.
- `npm run test:lint`: 11 pass, no skips. Covers config-derived exclusions,
  Svelte template protection, script rules, syntax rejection and a positive
  template-reference case.
- Before/after effective-config comparison: all 194 files pass. All original
  non-mapped active settings are retained; all original settings on 63 Svelte
  files are retained. The plain-script migration disables 8,813 duplicate
  rule/file pairs. This verifies configuration, not identical linter behavior.
- `npm run check`: zero errors and zero warnings.
- `npm test`: all 1,148 existing tests pass in 58 files.
- `npm run build`: passes.
- Python and product code do not change. No Python, browser or emulator run is
  claimed. No existing case, skip, deadline or retry changes.
- Self-review only. No subagent or separate reviewer was configured or used.

The raw evidence stays in the retained task workspace under
`.night-evidence/lr-347/lr-347.10.15/`: `runs.jsonl`, full command logs,
`baseline-active-rules.json`, `mapped-names.json`, `config-parity.json`,
`dependency-diff.json`, `compiler-probes.json`, `coverage-svelte-check-1.txt`,
`js-all-plugin-probes.json` and the scripts/fixtures that produced them.
The first native finding is kept in `first-oxlint.json`; its corrected result
is in `fixed-oxlint.json`. An initial probe-loader import error was corrected
by using the compiler's CommonJS default export. No app check was bypassed.

The local task bookmark is `lr-347.10.15`. The workspace and evidence are kept
for owner review. The run started from the accepted BA.1 revision. Another
session later advanced `integration` to BA.14 (`qkpuvtps / 31267e9c`). This
worker leaves that work alone and does not rebase its task line. No shared bookmark is moved by this worker. The parent task
forbids code publication, so only Beads data is synced. No code is pushed,
accepted or deployed. The owner decides acceptance; BA.16 can then change the
package manager without adopting the rejected Bun test-runner spike.
