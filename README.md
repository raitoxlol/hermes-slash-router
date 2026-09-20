# Hermes Slash Router

Hermes Desktop plugin: TypeSafe Jev routes misspelled, shortened, and meaning-based slash commands to real Hermes commands.

## Behavior

1. Exact live commands and native aliases pass through unchanged.
2. Saved Jev and correction decisions are kept as advisory context. Every later non-exact lookup still calls Jev; Jev can choose a different command or abstain.
3. Every other command token goes to Jev with the full current desktop command catalog. Jev handles spelling mistakes (`modle`), omitted-vowel shortcuts (`thnkin`, `wktr`), and meaning (`effort` → `reasoning`). The plugin has no local typo or meaning rules and no command approval list.
4. If Jev is unsure or unavailable, the draft stays put and a free-text “What did you mean?” prompt appears at the bottom of the composer. Explain the intended action in your own words. Jev interprets that explanation against the current command catalog. A choice needs confidence ≥ 0.85 and must be a real available command. On success, the token, Jev's selected command, and your explicit meaning are saved as reminders. Related spellings can receive up to eight recent corrections from the same profile and command catalog as context. Every later use is sent to Jev for a fresh decision; stored routes are never applied automatically. Press Send to run the original draft and arguments. If Jev is still unsure, it asks for a clearer explanation without saving a guess.

Arguments and attachments are preserved. Routing sends Jev the command token, current catalog, an optional exact-token reminder, and up to eight explicit correction examples scoped to the active profile and catalog. Arguments and conversation history are never sent. Clicking **Remember what I meant** saves that explanation (up to 500 characters) with the correction reminder; it is not copied to routing history. These are hints for Jev, not aliases or automatic routes. The plugin records Jev decisions, not proof that downstream commands succeeded: Hermes middleware has no execution-result hook.

Prior decisions persist in Hermes plugin storage, scoped by profile and catalog contents. The last 500 mappings and 200 history entries are retained. Jev and correction decisions are advisory hints only; every non-exact use is rechecked by Jev. Older local guesses are ignored. In ⌘K, use **Slash Router: copy routing history** or **Slash Router: forget the last route reminder**. Existing exact commands always pass through unchanged.

## Install

Run `python3 ~/Projects/hermes-slash-router/install.py` once. It refuses to overwrite an existing installation. Then use ⌘K → **Reload desktop plugins**. Exact valid commands need no Jev request; non-exact routing uses the enabled backend and its server-side API key.

For Jev, enable `hermes-slash-router` in the backend profile's `plugins.enabled` configuration, make `TYPESAFE_API_KEY` available to that gateway process, and restart the gateway when idle. The desktop toggle and backend allow-list are separate. The key stays server-side; do not put it in plugin.js or plugin storage. Remote gateways need the backend package installed and enabled on that remote host.

The pinned API model is `jev-1.13.0`; request timeout is 3 seconds. Each backend admits at most one Jev request per second, rejects bursts, and never automatically retries. Saved route records and explicit corrections are sent as optional reminder context; they never avoid a Jev call. Jev re-evaluates every non-exact token and may choose a different command or abstain. Live calls incur TypeSafe usage. The explanation is sent to Jev when taught and stored only because the user pressed **Remember what I meant**. Corrections use the existing `/resolve` route and send a normalized explanation token as well, so gateways that have not loaded the newer `/learn` endpoint can still process them. API errors fail closed with the original draft and explanation retained. If the command catalog itself cannot load, slash submissions are also retained until connectivity returns.

## Verification

`npm test --prefix ~/Projects/hermes-slash-router`

`~/.hermes/hermes-agent/.venv/bin/python -m unittest discover -s ~/Projects/hermes-slash-router/tests -p 'test_*.py'`

Tests use the actual plugin handler and mocked TypeSafe transport. A paid live Jev call and desktop end-to-end execution are separate checks, not covered by these tests.

Live Jev checks on 2026-09-20: ten sequential TypeSafe calls completed, including successful routes and safe abstentions. The installed backend handlers were also exercised with live Jev responses through FastAPI TestClient. Per-token response data stays local and is excluded from source control and installation.

End-to-end Hermes Desktop smoke test (2026-09-20): after reloading the desktop plugin, a previously saved `/mdl` decision still triggered a fresh Jev lookup and opened the native Switch model picker. After restarting the Max Gateway to load the updated backend, another `/mdl` again displayed `/mdl → /model (jev)` and opened the picker. I canceled both without changing the active model. A prior `/xyzzy` UI check kept the draft in the composer and showed the free-text “What did you mean?” prompt; a no-action explanation reached Jev and abstained without saving a mapping.

All 28 offline tests pass (19 JavaScript, 9 Python), including cross-spelling correction examples, profile/catalog scoping, fresh Jev decisions, argument preservation, privacy, abstention, and free-text clarification. Installed desktop copies and the backend package match their source hashes. The Hermes Desktop plugin reloaded and its palette actions remained available. The Max Gateway restarted under a new process and returned ready. The new correction generalization is covered with mocked Jev; no paid live correction call was made. Corrections saved by older versions do not contain the explanation, so teach that shortcut once more to enable related-spelling context.

References: [TypeSafe API quickstart](https://docs.typesafe.ai/introduction/quickstart), [Hermes Desktop SDK](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/desktop-plugin-sdk.md).
