import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";

export default definePluginEntry({
  id: "wiki-context-plugin",
  name: "Wiki Context Injector",
  description:
    "Runs wiki_context.py before every prompt and prepends relevant wiki pages as <wiki-context> block.",

  register(api) {
    // OpenClaw exposes plugin config as api.config (not api.getConfig())
    const cfg = ((api as Record<string, unknown>).config ?? {}) as {
      workspace?: string;
      wikiContextScript?: string;
      pythonExecutable?: string;
      k?: number;
      timeoutMs?: number;
      debug?: boolean;
    };

    const debug = cfg.debug === true;
    const log = (...args: unknown[]) => {
      if (debug) process.stderr.write("[wiki-context-plugin] " + args.join(" ") + "\n");
    };

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
    const timeoutMs = cfg.timeoutMs ?? 15_000;

    log(`registered — workspace=${workspace} script=${wikiContextScript} python=${python} k=${k} timeoutMs=${timeoutMs}`);

    api.on(
      "before_prompt_build",
      async (event) => {
        const ev = event as Record<string, unknown>;

        // Log all top-level keys in debug mode so we can find the right field name.
        log(`before_prompt_build fired — event keys: ${Object.keys(ev).join(", ")}`);

        // Try known field names across SDK versions.
        const userText: string =
          ev.userMessage as string ??
          ev.prompt as string ??
          ev.currentPrompt as string ??
          ev.input as string ??
          ev.message as string ??
          ev.text as string ??
          "";

        log(`userText extracted (${userText.length} chars): ${userText.slice(0, 80)}`);

        if (!userText.trim()) {
          log("userText is empty — skipping wiki_context.py call");
          return {};
        }

        let output = "";
        try {
          output = execFileSync(
            python,
            [
              wikiContextScript,
              "--workspace", workspace,
              "--q", userText,
              "--k", k,
            ],
            { encoding: "utf-8", timeout: timeoutMs }
          ).trim();

          log(`wiki_context.py returned ${output.length} chars`);
        } catch (err) {
          log(`wiki_context.py error: ${err}`);
          // Always fail silently — never block the user's prompt.
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
