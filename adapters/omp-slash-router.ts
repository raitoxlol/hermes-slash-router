import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

const SLASH = /^(\s*)\/([\w:-]+)(?=\s|$)([\s\S]*)$/;
const BUILTINS: Record<string, true> = {
  help: true, compact: true, model: true, new: true, fresh: true, clear: true,
  resume: true, fork: true, export: true, share: true, login: true, logout: true,
  pause: true, btw: true, memory: true, vibe: true, computer: true, restart: true,
  delete: true, skills: true, reload: true, "reload-plugins": true, status: true,
  undo: true, redo: true, copy: true, paste: true, diff: true, plan: true, goal: true,
  settings: true, config: true, theme: true, quit: true, exit: true, abort: true,
  stop: true, cost: true, usage: true, doctor: true, commands: true,
};


function hermesTypeSafeKey(): string | undefined {
  if (process.env.TYPESAFE_API_KEY) return process.env.TYPESAFE_API_KEY;
  const home = process.env.HOME || homedir();
  const files = [
    process.env.HERMES_HOME ? join(process.env.HERMES_HOME, ".env") : "",
    join(home, ".hermes", "profiles", "max", ".env"),
    join(home, ".hermes", ".env"),
  ].filter(Boolean);
  for (const file of files) {
    if (!existsSync(file)) continue;
    let text = "";
    try {
      text = readFileSync(file, "utf8");
    } catch {
      continue;
    }
    for (const raw of text.split("\n")) {
      const line = raw.trim();
      if (!line || line.startsWith("#")) continue;
      const body = line.startsWith("export ") ? line.slice(7) : line;
      if (!body.startsWith("TYPESAFE_API_KEY=")) continue;
      let value = body.slice("TYPESAFE_API_KEY=".length).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      if (value) return value;
    }
  }
  return undefined;
}

function resolveToken(token: string): { target?: string; ok?: boolean } | null {
  const key = hermesTypeSafeKey();
  if (!key) return null;
  const result = spawnSync("slash-route", ["resolve", "--surface", "omp", token], {
    encoding: "utf8",
    timeout: 8000,
    env: { ...process.env, TYPESAFE_API_KEY: key },
  });
  if (result.status !== 0 && result.status !== 2) return null;
  try {
    return JSON.parse(result.stdout || "{}");
  } catch {
    return null;
  }
}

function commandNames(pi: ExtensionAPI): Record<string, true> {
  const names: Record<string, true> = { ...SKIP, ...BUILTINS };
  try {
    const commands = pi.getCommands?.() ?? [];
    for (const command of commands) {
      const raw = String(
        (command as { name?: string; command?: string }).name ||
          (command as { command?: string }).command ||
          "",
      )
        .toLowerCase()
        .replace(/^\//, "");
      if (!raw) continue;
      names[raw] = true;
      names[raw.replace(/-/g, "_")] = true;
      names[raw.replace(/_/g, "-")] = true;
    }
  } catch {
    return names;
  }
  return names;
}


export default function slashRouter(pi: ExtensionAPI) {
  // Runs on submit, before slash dispatch. Unknown /typo is rewritten to the
  // real command so OMP executes it as if it was typed correctly.
  pi.on("input", async (event) => {
    const match = SLASH.exec(event.text || "");
    if (!match) return;
    const token = match[2].toLowerCase();
    if (SKIP[token.split(":")[0]]) return;
    const known = commandNames(pi);
    if (known[token] || known[token.replace(/-/g, "_")] || known[token.replace(/_/g, "-")]) {
      return;
    }
    const decision = resolveToken(token);
    if (!decision?.ok || !decision.target || decision.target === token) return;
    return { text: `${match[1]}/${decision.target}${match[3]}` };
  });
}
