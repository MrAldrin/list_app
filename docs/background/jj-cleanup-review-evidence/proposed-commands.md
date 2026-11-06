# Exact proposed commands

Not approved for live execution. The owner must select each exact set first.
Recheck IDs, protected state, ancestry and archive checksum in the exclusive graph window.
No push or source retirement is implied by a successful disposable test.

## Conditional local-name removal

```sh
jj bookmark forget exact:reminders-s2
```

Recovery (separate coordinated operation, only if needed):

```sh
jj bookmark set reminders-s2 -r e50da7ce0a5456159f8206513c820e7180abbb8e
```

## A — nine independent empty leaves, then one two-empty tail

```sh
jj abandon -r 2f94b979c91a7031ae821bcb00cfe95b4ec101bb
```

```sh
jj abandon -r e94ba514857ad7fdb15eebc304dc927c5f281aa5
```

```sh
jj abandon -r 8bb5563fdf96e060594187d4621ab864bfd78895
```

```sh
jj abandon -r 2b7b53a00395e6ac3526f97e5df58b4f615d290d
```

```sh
jj abandon -r 4c653c9ea1e0aee85dee2aa82e89b76873da8f8a
```

```sh
jj abandon -r 0aee179f4691eb701307a4a20c28acccac2bef07
```

```sh
jj abandon -r d49ce34494232c50ed8b6558dcec7392b7de3153
```

```sh
jj abandon -r 0ba13f05e82f9fd9a1dac13a95e2cf5564ad555b
```

```sh
jj abandon -r c650413ba10c240af0c50f2359691a2ae8ab3d59
```

Retire the final two-empty tail together so its parent is not exposed:

```sh
jj abandon -r 095fe95ea6724b191d8d3d6707575e4eca8bd106 -r 95b1f504bd343cd74c464d39314ed1efa09d34df
```

## B — separately approved divergent leaf retirement

```sh
jj abandon -r d8e8f9946cce76c82c06ad6c2533cc213a42ca2c
```

```sh
jj abandon -r 31077a91123572b05e77baa41be804c6347967bb
```

No C command is selected. No command may target retained sibling versions or protected workspace heads. Abandonment does not guarantee Git object retention; the tested native archive is the durable recovery artifact.
