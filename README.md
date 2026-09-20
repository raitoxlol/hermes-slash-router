# Hermes Slash Router

Unified Hermes Agent and Desktop plugin: TypeSafe Jev routes misspelled, shortened, and meaning-based slash commands to real Hermes commands.

<a href="hermes://plugin/install?repo=raitoxlol/hermes-slash-router&enable=1">Install in Hermes</a> — or run `hermes plugins install raitoxlol/hermes-slash-router`.

## Requirements

- Hermes Agent >= 0.21.2.
- A `TYPESAFE_API_KEY` for TypeSafe Jev. Every non-exact slash token is routed by a billed API call. With no key the plugin stays inert: it fails closed and your draft is left alone.

## Behavior

1. Exact live commands and native aliases pass through unchanged.
2. Saved Jev and correction decisions are kept as advisory context. Every later non-exact lookup still calls Jev; Jev can choose a different command or abstain.
3. Every other command token goes to Jev with the full current desktop command catalog. Jev handles spelling mistakes (`modle`), omitted-vowel shortcuts (`thnkin`, `wktr`), and meaning (`effort` → `reasoning`). The plugin has no local typo or meaning rules and no command approval list.
4. If Jev is unsure or unavailable, the draft stays put and a free-text “What did you mean?” prompt appears at the bottom of the composer. Explain the intended action in your own words. Jev interprets that explanation against the current command catalog. A choice needs confidence ≥ 0.85 and must be a real available command. On success, the token, Jev's selected command, and your explicit meaning are saved as reminders. Related spellings can receive up to eight recent corrections from the same profile and command catalog as context. Every later use is sent to Jev for a fresh decision; stored routes are never applied automatically. Press Send to run the original draft and arguments. If Jev is still unsure, it asks for a clearer explanation without saving a guess.

Arguments and attachments are preserved. Routing sends Jev the command token, current catalog, an optional exact-token reminder, and up to eight explicit correction examples scoped to the active profile and catalog. Arguments and conversation history are never sent. Clicking **Remember what I meant** saves that explanation (up to 500 characters) with the correction reminder; it is not copied to routing history. These are hints for Jev, not aliases or automatic routes. The plugin records Jev decisions, not proof that downstream commands succeeded: Hermes middleware has no execution-result hook.

Prior decisions persist in Hermes plugin storage, scoped by profile and catalog contents. The last 500 mappings and 200 history entries are retained. Jev and correction decisions are advisory hints only; every non-exact use is rechecked by Jev. Older local guesses are ignored. In ⌘K, use **Slash Router: copy routing history** or **Slash Router: forget the last route reminder**. Existing exact commands always pass through unchanged.

## Install

Verified target: Hermes Agent v0.21.2.

```bash
hermes plugins install raitoxlol/hermes-slash-router
hermes plugins enable hermes-slash-router
```

Then rescan or reload Hermes Desktop (⌘K → **Rescan desktop plugins**) and enable Slash Router in **Capabilities → Plugins**. Both halves ship off and stay off until you enable them. It is one installable folder, `plugins/hermes-slash-router/`; Hermes Desktop copies its `desktop/plugin.js` half into `desktop-plugins/` for you.

Working from a checkout instead? `python3 install.py` copies the same unified package into `$HERMES_HOME/plugins/hermes-slash-router` — set `HERMES_HOME` to target a profile. It refuses to overwrite an existing package, or a hand-placed standalone Desktop copy; back those up and remove them first.

The manifest declares `TYPESAFE_API_KEY` as a required secret, and the hosted Hermes install flow prompts for it. The local copy installer never reads or writes credentials; for a local install, provide the key to the gateway through your normal secret setup. Do not put it in plugin.js or plugin storage. Remote gateways need the agent package installed and enabled on that remote host.

The pinned API model is `jev-1.13.0`; request timeout is 3 seconds. Each backend admits at most one Jev request per second, rejects bursts, and never automatically retries. Saved route records and explicit corrections are sent as optional reminder context; they never avoid a Jev call. Jev re-evaluates every non-exact token and may choose a different command or abstain. Live calls incur TypeSafe usage. The explanation is sent to Jev when taught and stored only because the user pressed **Remember what I meant**. Corrections use the existing `/resolve` route and send a normalized explanation token as well, so gateways that have not loaded the newer `/learn` endpoint can still process them. API errors fail closed with the original draft and explanation retained. If the command catalog itself cannot load, slash submissions are also retained until connectivity returns.

## Verification

Run these from the repository root:

`npm test`

`python3 -m unittest discover -s tests -p 'test_*.py'`

The Python checks need FastAPI and Pydantic, supplied by a Hermes Agent Python environment.

Tests use the actual plugin handler and mocked TypeSafe transport. A paid live Jev call and desktop end-to-end execution are separate checks, not covered by these tests.

Live Jev checks on 2026-09-20: ten sequential TypeSafe calls completed, including successful routes and safe abstentions. The installed backend handlers were also exercised with live Jev responses through FastAPI TestClient. Per-token response data stays local and is excluded from source control and installation.

End-to-end Hermes Desktop smoke test (2026-09-20): after reloading the desktop plugin, a previously saved `/mdl` decision still triggered a fresh Jev lookup and opened the native Switch model picker. After restarting the Max Gateway to load the updated backend, another `/mdl` again displayed `/mdl → /model (jev)` and opened the picker. I canceled both without changing the active model. A prior `/xyzzy` UI check kept the draft in the composer and showed the free-text “What did you mean?” prompt; a no-action explanation reached Jev and abstained without saving a mapping.

The offline tests cover cross-spelling correction examples, profile/catalog scoping, fresh Jev decisions, argument preservation, privacy, abstention, free-text clarification, and unified-package installation. The Hermes Desktop plugin reloaded and its palette actions remained available. The Max Gateway restarted under a new process and returned ready. The new correction generalization is covered with mocked Jev; no paid live correction call was made. Corrections saved by older versions do not contain the explanation, so teach that shortcut once more to enable related-spelling context.

Possible next directions beyond slash commands are in [ROADMAP.md](ROADMAP.md); they are proposals, not shipped behavior.

References: [TypeSafe API quickstart](https://docs.typesafe.ai/introduction/quickstart), [Hermes Desktop SDK for v0.21.2](https://github.com/NousResearch/hermes-agent/blob/v2026.9.11/website/docs/developer-guide/desktop-plugin-sdk.md).

## License

MIT — see [LICENSE](LICENSE).
