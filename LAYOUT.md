# Public HACS package — naming & git

## Names

| Where | Name |
|-------|------|
| **Gitea** | [`HA_SPR-SUN`](https://git.erhancm.com/erhan/HA_SPR-SUN) — full monorepo |
| **GitHub** | [`ha-sprsun`](https://github.com/erhancm/ha-sprsun) — HACS package |
| **HACS display name** | SPRSUN |
| **HA domain** | `sprsun` |

The vendor protocol document code (CG248075) stays in register filenames and
compatibility notes when you need to name the exact PDF — not in the product
name.

## Two repositories (not a mirror)

```text
Gitea  HA_SPR-SUN          GitHub  ha-sprsun
─────────────────          ────────────────
everything                 only github-hacs/ contents
docs, scripts, Arduino  →  README, component, registers, examples
github-hacs/ (staging)
```

1. Develop in the monorepo (`home-assistant/custom_components/sprsun`, …).
2. Refresh the export: `python scripts/sync_github_hacs.py`
3. Copy the contents of `github-hacs/` into a sibling clone of
   `https://github.com/erhancm/ha-sprsun.git`, then commit / tag / push there.

## Local layout

```text
Variant Projects/
├── SPRSUN/           ← this monorepo (Gitea)
│   └── github-hacs/  ← staging (no nested .git)
└── ha-sprsun/        ← separate clone of GitHub (sibling folder)
```

Keep **one** git root for the monorepo. Do not nest `.git` inside `github-hacs/`.

## CI on GitHub (`ha-sprsun`)

Two workflows run on push / PR / nightly / manual dispatch:

| Workflow | Purpose |
|----------|---------|
| `.github/workflows/hassfest.yml` | Home Assistant integration validator |
| `.github/workflows/hacs.yml` | Same checks HACS uses for default-store inclusion |

Both must stay green before opening a PR to [`hacs/default`](https://github.com/hacs/default). Cut a new GitHub **Release** after they pass.
