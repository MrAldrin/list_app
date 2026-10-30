# ListR documentation

Start here for current product behavior, developer guides, operations, and the
project's work agenda. The [architecture](../ARCHITECTURE.md) is the source of
truth for the stack and major decisions; this hub links to it rather than
copying it.

## Using ListR

- [Public list sharing](public-sharing.md) and [room invitations](room-invitations.md)
- [Offline use](offline-viewing.md), [change tracking](change-tracking.md), and
  [item writes](item-writes.md)
- [Checked-item visibility](checked-item-visibility.md),
  [item sorting](item-sorting.md), and
  [home-screen installation](home-screen-installation.md)
- [JSON API](api.md)

## Development and operations

- [Local setup and app development](../README.md)
- [Deployment, backups, and recovery](deployment.md)
- Tests: [real browsers](browser-testing.md),
  [Android emulator](android-emulator-testing.md), and
  [phone over the network](local-network-testing.md)
- [Scope and approval gates](scope.md)
- [Agent rules](../AGENTS.md)

## Work and proposals

The [backlog](../plans/backlog.md) is the sole work agenda. The
[improvement ideas](../plans/improvement-ideas.md) plan is a proposal catalog;
its recommendations and open questions do not select work. Only items moved to
the backlog by an owner decision become selected work.

## Local site preview only

The generated site includes current guides, operational instructions,
historical research under `docs/background/`, and planning documents. In
particular, the [phone-testing guide](local-network-testing.md) contains private
Tailscale addresses, a hostname, and firewall details. This material has not
been reviewed for public release. The local preview is not publication
approval; get an owner review before exposing or publishing the generated site.
See the README's [local documentation preview](../README.md#documentation-preview-local-only)
for build instructions.
