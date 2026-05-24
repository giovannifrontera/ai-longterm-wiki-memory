import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { existsSync, writeFileSync } from "node:fs";

const execFileAsync = promisify(execFile);

export default definePluginEntry({
  id: "wiki-context-plugin",
  name: "Wiki Context Injector",
  description:
    "Runs wiki_context.py before every prompt and prepends relevant wiki pages as <wiki-context> block.",

  register(api) {
    // OpenClaw passes plugin-specific config via api.pluginConfig, not api.config
    const cfg = ((api as Record<string, unknown>).pluginConfig ?? {}) as {
      workspace?: string;
      wikiContextScript?: string;
      pythonExecutable?: string;
      k?: number;
      maxChars?: number;
      timeoutMs?: number;
      debug?: boolean;
    };

    const debug = cfg.debug === true;

    console.log("[wiki-context-plugin] registering — pluginConfig keys:", Object.keys(cfg).join(", "));

    if (!cfg.workspace || !cfg.wikiContextScript) {
      console.warn(
        "[wiki-context-plugin] Missing required config: workspace and wikiContextScript must be set."
      );
      return;
    }

    const workspace = cfg.workspace;
    const wikiContextScript = cfg.wikiContextScript;

    if (!existsSync(wikiContextScript)) {
      console.warn(
        `[wiki-context-plugin] wiki_context.py not found at: ${wikiContextScript}`
      );
      return;
    }

    const python = cfg.pythonExecutable ?? "python";
    const k = String(cfg.k ?? 3);
    const maxChars = String(cfg.maxChars ?? 600);
    const timeoutMs = cfg.timeoutMs ?? 15_000;
    const debugLog = `${workspace}/.wiki-plugin-debug.log`;

    console.log(`[wiki-context-plugin] registered — workspace: ${workspace}, k: ${k}`);

    api.on(
      "before_prompt_build",
      async (event) => {
        console.log("[wiki-context-plugin] hook fired");

        const ev = event as Record<string, unknown>;
        const eventKeys = Object.keys(ev).join(", ");

        // Try known field names across SDK versions.
        const userText: string =
          ev.userMessage as string ??
          ev.prompt as string ??
          ev.currentPrompt as string ??
          ev.input as string ??
          ev.message as string ??
          ev.text as string ??
          "";

        console.log(`[wiki-context-plugin] event keys: ${eventKeys} | userText length: ${userText.length}`);

        if (!userText.trim()) {
          if (debug) {
            try {
              writeFileSync(debugLog,
                `[${new Date().toISOString()}] hook fired but userText empty\nevent keys: ${eventKeys}\n`, "utf-8");
            } catch {}
          }
          return {};
        }

        let output = "";
        let errorMsg = "";
        try {
          const result = await execFileAsync(
            python,
            [
              wikiContextScript,
              "--workspace", workspace,
              "--q", userText,
              "--k", k,
              "--max-chars", maxChars,
            ],
            { encoding: "utf-8", timeout: timeoutMs }
          );
          output = result.stdout.trim();
        } catch (err) {
          errorMsg = String(err);
          console.error(`[wiki-context-plugin] execFile error: ${errorMsg}`);
          // Always fail silently — never block the user's prompt.
        }

        console.log(`[wiki-context-plugin] output length: ${output.length}`);

        if (debug) {
          try {
            writeFileSync(debugLog,
              `[${new Date().toISOString()}]\n` +
              `event keys: ${eventKeys}\n` +
              `userText (${userText.length} chars): ${userText.slice(0, 120)}\n` +
              `output (${output.length} chars): ${output.slice(0, 200)}\n` +
              (errorMsg ? `error: ${errorMsg}\n` : ""), "utf-8");
          } catch {}
        }

        if (output) {
          return { prependContext: output };
        }

        return {};
      },
      { priority: 50, timeoutMs: timeoutMs + 5_000 }
    );
  },
});
