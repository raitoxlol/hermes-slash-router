# Hermes Slash Router

A standalone Hermes Desktop plugin: TypeSafe Jev routes misspelled, shortened, and meaning-based slash commands against Desktop's live command catalog.

[Install in Hermes](hermes://plugin/install?repo=raitoxlol/hermes-slash-router&enable=1), or run `hermes plugins install raitoxlol/hermes-slash-router`.

## Requirements

- Hermes Desktop with Hermes Agent >= 0.21.2.
- `TYPESAFE_API_KEY` in the backend environment. Every non-exact lookup incurs paid TypeSafe API usage. Without a usable key, the original draft stays in the composer.

## Install

```bash
hermes plugins install raitoxlol/hermes-slash-router
hermes plugins enable hermes-slash-router
```

Then rescan Desktop plugins and enable **Slash Router · Jev** in **Capabilities → Plugins**. Restart the backend after configuring the key.

One package contains `desktop/plugin.js` and a small HTTP backend under `dashboard/`. Hermes installs the Desktop half automatically. The backend keeps the TypeSafe key out of the renderer; it registers no agent commands, tools, hooks, or middleware. On a remote connection, install and enable the backend package on that host too.

The hosted install flow prompts for the required secret. For a local checkout, `python3 install.py` copies the package into `$HERMES_HOME/plugins/hermes-slash-router`. It refuses to overwrite an existing installation and never manages credentials. Supply the key through your normal Hermes secret setup; never put it in `plugin.js` or plugin storage.

## Behavior

1. Exact live commands and native aliases pass through unchanged. Every other supported slash token goes to Jev with the current Desktop command catalog.
2. Jev may choose only an offered command at confidence >= 0.85. If uncertain or unavailable, the draft stays put and a bottom **What did you mean?** field accepts an explanation.
3. **Remember what I meant** saves an explicit correction as advisory context. Up to eight examples from the same profile and command catalog may help with related spellings. Every later non-exact use gets a fresh Jev decision; saved reminders never automatically execute a route.

Arguments and attachments are preserved. Jev receives the token, command catalog, optional prior decision, and correction examples. Arguments and conversation history are not sent. Correction explanations are at most 500 characters and are excluded from the routing-history export.

Reminders live in Desktop plugin storage, keyed by profile and catalog fingerprint. The last 500 reminders and 200 history entries are retained. Use the command palette to **copy routing history** or **forget the last route reminder**.

The backend uses `jev-1.13.0`, a three-second timeout, and at most one request per second with no automatic retries. The key-status indicator reports loaded, saved in the active profile but requiring restart, or missing. It never returns the key value.

## Version 0.3.0 scope

This release routes only Hermes Desktop composer submissions. Earlier CLI/gateway hooks, `/route`, portable CLI, bundled catalogs, shared Python history, and Claude/OMP adapters have been removed. Their previous implementation remains in Git history. Existing installations must update and restart their backend to unload the earlier CLI hook.

## Verification

```bash
npm test
python3 -m unittest discover -s tests -p 'test_*.py'
hermes plugins validate .
```

Python tests need FastAPI and Pydantic from the Hermes backend environment. Tests exercise the actual Desktop handler and backend with simulated TypeSafe responses, including profile/catalog scoping, argument preservation, safe abstention, correction privacy, and installation. Paid live calls and a fresh Desktop UI smoke test are separate checks.

Possible future Desktop features are in [ROADMAP.md](ROADMAP.md).

MIT — see [LICENSE](LICENSE).
