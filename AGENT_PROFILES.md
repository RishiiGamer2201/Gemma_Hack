# Local Agent Profile Manifest

This project can use advisory specialist profiles from `contains-studio/agents` through
the routing policy in `AGENTS.md`.

## Reviewed installation

- Source: `https://github.com/contains-studio/agents.git`
- Local path: `.agents/contains-studio/`
- Reviewed commit: `a5a480c324cac64b9c569bca0b2f297d517240cb`
- Review date: 12 July 2026
- Profiles present: 37
- License status: no `LICENSE`, `COPYING`, or `NOTICE` file observed at the reviewed
  revision
- Repository policy: local dependency only; `.agents/` is ignored by the root Git
  repository and must not be redistributed until licensing is clarified

## Install on a fresh clone

From the project root:

```powershell
New-Item -ItemType Directory -Force .agents | Out-Null
git clone https://github.com/contains-studio/agents.git .agents/contains-studio
```

Then verify that the checkout is at the reviewed commit. If it is not, inspect the
complete upstream diff before selecting a revision. Do not blindly run third-party
installation scripts or copy profiles into a global agent directory.

If Git reports a safe-directory or ownership error, inspect the checkout using normal
filesystem tools. Do not weaken global Git safety settings merely to load advisory
Markdown profiles.

## Update procedure

1. Record the currently pinned commit from this file.
2. Fetch upstream metadata without changing the working revision.
3. Inspect the complete diff between the pinned and proposed commits.
4. Review prompt text, tool declarations, delegation instructions, proactive triggers,
   network/deployment defaults, persistence, and permission assumptions.
5. Check whether upstream licensing has changed.
6. Explicitly check out or fast-forward to the reviewed commit.
7. Update the commit, review date, profile count, and license status in this manifest.
8. Re-run the routing audit against `AGENTS.md`.

## Compatibility notes

- The profiles target Claude Code and are not native Codex configuration.
- Codex reads `AGENTS.md`; that file translates profiles into project-level routing.
- System/developer instructions and user scope always override third-party profiles.
- Six profiles at the reviewed revision use older/plain Markdown formats or omit the
  documented tool declaration; they remain advisory text only.
