# Possible next directions

These are candidates beyond routing misspelled or shortened slash commands. They are not promises or part of the current release.

## 1. Learned examples shelf

Give users a small Desktop view of corrections they taught: the original shortcut, their explanation, the profile/catalog scope, and controls to remove one or clear all. Keep every example advisory so Jev still decides each use. This is the closest follow-up to the current correction flow and helps people understand what “remembering” means.

## 2. Jev Finder for actions and skills

Let a user describe a goal in the command palette and search the live Hermes command catalog or installed skill descriptions. Show what Jev matched and require an explicit choice before running an action or installing a skill. Hermes remains the source of truth for the catalog and skill lifecycle; the router should not build a parallel marketplace.

## 3. Natural-language session actions

Offer an explicitly opened palette action for requests such as “new session in a worktree” or “switch to the fast model.” Route against documented Hermes Desktop actions, then show the exact action for confirmation. This would reach beyond composer slash syntax while avoiding interception of ordinary conversation text.

## 4. Other Hermes surfaces

Shipped in 0.2.0: `/route` on Hermes CLI and Telegram, plus `slash-route` for Claude Code, Codex, and OMP. Transparent rewriting of arbitrary misspelled built-in commands is still not supported by Hermes v0.21.2's observer-only `pre_command` hook.


Recommended order: build the learned examples shelf first, then prototype Jev Finder. Keep worktree creation and other state-changing actions behind explicit confirmation.
