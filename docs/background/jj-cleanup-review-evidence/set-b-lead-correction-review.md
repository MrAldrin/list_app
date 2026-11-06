# Set B: independent Lead static correction

**PASS.** Lead session `01a1ad8b-c485-774e-bb47-66e425c18dc4` independently executed a bounded Python-only audit on six explicit frozen files. This was not the Conductor's parser. The verdict was returned through Pi Intercom after the Haiku correction parser failed.

## Computed checks

- Historical parent-map SHA matches. Its 988 entries, minus exact A11 and B2 only (excluding C), yield 975 visible entries and 16 heads. These equal the frozen B manifest and provenance record.
- Actual B-before has 983 entries. Removing exact B2 yields actual after with 981 entries. Graph-recomputed heads are 18 → 16 and match the before, after and provenance records. Retained parent lists are unchanged.
- Exactly 14 head IDs are shared. Only the two documented workspace cursors differ.
- Historical parent lists match the parent map. The historical workspace receipt confirms owner labels and abbreviated change IDs.
- Both replacement rows match actual B-before, have the same full change IDs and parents as the supplied historical rows, and are ancestors of the current cursors.
- All assertions passed. No jj, Git, config, network or source-write commands were run.

## Limits and disposition

Full historical change-ID rows came from the Conductor's native-read provenance record. Historical workspace abbreviations and the parent map corroborate them. The Lead did not perform a fresh native historical read.

This correction closes the historical-versus-live provenance question. It does not replace Haiku's independently executed 20-file hash, two-full-map, exact-flag, 79-tree and descendant-set audit. Preserve the original narrow BLOCK and partial correction BLOCK. Do not label either as a Haiku PASS or a native rerun. No Grok escalation was needed.

## Frozen input SHA-256 values

| Input | SHA-256 |
| --- | --- |
| `set-b-head-provenance.json` | `7bfedf53bbe0c012e81b04fbf7e4349b66613926ca6de97c9652710f224441a4` |
| `proposed-exact-sets.json` | `e891b74e15bc090002ad55c696821695e60a8bff40e8881d8ac925d9dd257e49` |
| `current-workspaces.txt` | `7e8285c66779eb6f16e5eb63819623e157f4963aa6344d87de05d37f3736d1b5` |
| Private B `before.json` | `9736b3fbe303998096ce5424170164e9236b26ed21611c3f04e20c16093b1197` |
| Private B `after.json` | `52283ac41f5bc8692ac724594196045304c6fbdbf35d75fe8581b73adb59217e` |
| Private `historical-f6-parent-map.json` | `217918abf567e575811a3bae800012c74fcf5442f0aa5161a296a9a055537116` |
