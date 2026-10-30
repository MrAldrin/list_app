# Preview exclusions

The local Zensical preview excludes the content of
`docs/local-network-testing.md` and `docs/background/`. Those source files remain
unchanged in the repository. The network guide contains private connection
details. The background folder holds internal historical, operational, and
research evidence.

Links to excluded pages and evidence folders redirect here so the preview can
explain the omission without copying that source content. Redirects discard the
old section fragment; they do not provide the original page.

Zensical checks source links before it generates these redirects, so it reports
excluded targets as missing pages. The local build wrapper checks generated
routes and anchors afterward; it does not suppress Zensical's other link
checks. The search index omits excluded pages but may retain references to their
filenames from included sources.

Other operational guides and work plans remain in the preview. This output has
not been reviewed for public release and is not publication approval.
