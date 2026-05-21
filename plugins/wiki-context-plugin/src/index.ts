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
      maxChars?: number;
      timeoutMs?: number;
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
    const maxChars = String(cfg.maxChars ?? 600);
    const timeoutMs = cfg.timeoutMs ?? 15_000;

    api.on(
      "before_prompt_build",
      async (event) => {
        // NOTE: The exact field name for the user's message text depends on the
        // OpenClaw SDK version. Check your SDK's TypeScript types if this returns
        // an empty string. Common alternatives: event.prompt, event.userMessage,
        // event.currentPrompt, event.input.
        const userText: string =
          (event as Record<string, unknown>).userMessage as string ??
          (event as Record<string, unknown>).prompt as string ??
          (event as Record<string, unknown>).currentPrompt as string ??
          (event as Record<string, unknown>).input as string ??
          "";

        if (!userText.trim()) return {};

        try {
          const output = execFileSync(
            python,
            [
              wikiContextScript,
              "--workspace", workspace,
              "--q", userText,
              "--k", k,
              "--max-chars", maxChars,
            ],
            { encoding: "utf-8", timeout: timeoutMs }
          ).trim();

          if (output) {
            return { prependContext: output };
          }
        } catch {
          // Always fail silently — never block the user's prompt.
        }

        return {};
      },
      { priority: 50, timeoutMs: timeoutMs + 5_000 }
    );
  },
});
