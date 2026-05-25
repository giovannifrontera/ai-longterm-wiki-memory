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

    // Startup: verify python can import lancedb (fail silently, warn loudly)
    void (async () => {
      try {
        await execFileAsync(python, ["-c", "import lancedb"], { timeout: 10_000 });
      } catch {
        const msg =
          `[wiki-context-plugin] WARNING: '${python}' cannot import lancedb.\n` +
          `Wiki context will not be injected. Set 'pythonExecutable' to the absolute path.\n` +
          `Find the correct path: ${python} -c "import sys; print(sys.executable)"`;
        console.warn(msg);
        if (debug) {
          try {
            writeFileSync(debugLog, `[${new Date().toISOString()}] STARTUP FAIL\n${msg}\n`, "utf-8");
          } catch {}
        }
      }
    })();

    api.on(
      "before_prompt_build",
      async (event) => {
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
          // Always fail silently — never block the user's prompt.
        }

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

    // Tool: wiki_process_raw — promote raw/ files to the index
    // Exposed so OpenClaw agents can trigger it from chat
    if (typeof (api as Record<string, unknown>).registerTool === "function") {
      const apiAny = api as unknown as Record<string, (...args: unknown[]) => unknown>;
      apiAny.registerTool(
        "wiki_process_raw",
        async (params: { project?: string }) => {
          // wiki.py lives next to wiki_context.py in the same scripts/ directory
          const wikiPy = wikiContextScript.replace(/wiki_context\.py$/, "wiki.py");
          const args = ["process-raw", "--workspace", workspace];
          if (params?.project) {
            args.push("--project", params.project);
          }
          try {
            const { stdout } = await execFileAsync(python, [wikiPy, ...args], {
              encoding: "utf-8",
              timeout: 120_000,
            });
            return JSON.parse(stdout);
          } catch (err) {
            return { status: "error", message: String(err) };
          }
        }
      );
    }
  },
});
