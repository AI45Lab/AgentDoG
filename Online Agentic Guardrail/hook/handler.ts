/**
 * Guardrail PRE_REPLY Hook — thin HTTP client.
 *
 * All evaluation logic lives in the guardrail HTTP service.
 * This hook only:
 *   1. Reads the current session's events JSONL
 *   2. POSTs it to the guardrail service
 *   3. Blocks the reply if the service returns unsafe
 *
 * Works with any guardrail service instance — local or remote.
 */

import { readFileSync, existsSync, readdirSync, statSync } from "fs";
import { join } from "path";
import { homedir } from "os";

// --- Config ---

interface HookConfig {
  guardrail_url: string;
  sessions_dir: string;
  timeout_ms: number;
}

function loadConfig(): HookConfig {
  const defaults: HookConfig = {
    guardrail_url: "http://127.0.0.1:8340",
    sessions_dir: "~/.openclaw/agents/*/sessions",
    timeout_ms: 60000,
  };
  try {
    const configPath = join(
      import.meta.url.replace("file://", "").replace(/\/[^/]+$/, ""),
      "config.json",
    );
    if (existsSync(configPath)) {
      return { ...defaults, ...JSON.parse(readFileSync(configPath, "utf-8")) };
    }
  } catch {}
  return defaults;
}

function resolveHome(p: string): string {
  return p.startsWith("~/") ? join(homedir(), p.slice(2)) : p;
}

function expandSessionDirs(patterns: string): string[] {
  const dirs: string[] = [];
  for (const raw of patterns.split(",")) {
    const pattern = resolveHome(raw.trim());
    if (!pattern) continue;
    if (!pattern.includes("*")) {
      if (existsSync(pattern) && statSync(pattern).isDirectory()) dirs.push(pattern);
      continue;
    }
    const [before, after] = pattern.split("*", 2);
    const base = before.replace(/\/+$/, "");
    if (!existsSync(base) || !statSync(base).isDirectory()) continue;
    for (const name of readdirSync(base)) {
      const candidate = `${before}${name}${after || ""}`;
      if (existsSync(candidate) && statSync(candidate).isDirectory()) {
        dirs.push(candidate);
      }
    }
  }
  return dirs;
}

function findSessionEventsPath(patterns: string, sessionKey: string): string | null {
  for (const sessionsDir of expandSessionDirs(patterns)) {
    const eventsPath = join(sessionsDir, `${sessionKey}.jsonl`);
    if (existsSync(eventsPath)) return eventsPath;
  }
  return null;
}

// --- Hook Handler ---

const config = loadConfig();

const handler = async (event: any) => {
  const sessionKey = event.sessionKey || event.sessionId || "";
  if (!sessionKey) return;

  try {
    // Read session events JSONL
    const eventsPath = findSessionEventsPath(config.sessions_dir, sessionKey);
    if (!eventsPath) return;

    const sessionEvents = readFileSync(eventsPath, "utf-8");
    if (!sessionEvents.trim()) return;

    console.error(`[GUARDRAIL] Evaluating session ${sessionKey}`);

    // POST to guardrail service
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), config.timeout_ms);

    try {
      const response = await fetch(`${config.guardrail_url}/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_events: sessionEvents }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Service returned ${response.status}`);
      }

      const result = (await response.json()) as any;

      if (result.prediction === 1) {
        console.error(`[GUARDRAIL] BLOCKED: ${result.reason}`);
        if (event.messages) {
          event.messages.push(
            "[GUARDRAIL BLOCKED] The original agent reply was not delivered because the trajectory may be unsafe.",
          );
        }
        return { cancel: true };
      }

      console.error(`[GUARDRAIL] PASSED: ${result.reason}`);
    } finally {
      clearTimeout(timeout);
    }
  } catch (err: any) {
    // Fail-open: never block on guardrail errors
    console.error(`[GUARDRAIL] Error (fail-open): ${err.message || err}`);
  }
};

export default handler;
