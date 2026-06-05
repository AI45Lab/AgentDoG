import { t as definePluginEntry } from "../../plugin-entry-DhR2SXKx.js";

const GUARDRAIL_URL = process.env.GUARDRAIL_URL || "http://127.0.0.1:8340";

async function callGuardrail(trajectory, toolList) {
  try {
    const resp = await fetch(GUARDRAIL_URL + "/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trajectory, tool_list: toolList }),
    });
    return await resp.json();
  } catch (e) {
    return { prediction: -1, label: "error", reason: String(e).substring(0, 200) };
  }
}

export default definePluginEntry({
  register(api) {
    const trajectoryLines = [];
    const toolNames = new Set();

    api.on("before_agent_start", async () => {
      trajectoryLines.length = 0;
      toolNames.clear();
    });

    api.on("llm_input", async (event) => {
      if (event.prompt) {
        trajectoryLines.push("[USER] " + event.prompt.substring(0, 1000));
      }
    });

    api.on("before_tool_call", async (event) => {
      const tool = event.toolName || "?";
      const args = JSON.stringify(event.params || {}).substring(0, 500);
      trajectoryLines.push("[TOOL_CALL: " + tool + "] " + args);
      toolNames.add(tool);
    });

    api.on("after_tool_call", async (event) => {
      const tool = event.toolName || "?";
      const out = String(event.output || "").substring(0, 500);
      trajectoryLines.push("[TOOL_RESULT: " + tool + "] " + out);
    });

    api.on("llm_output", async (event) => {
      const text = (event.assistantTexts || []).join("\n");
      if (text) {
        trajectoryLines.push("[ASSISTANT] " + text.substring(0, 2000));
      }
    });

    api.on("message_sending", async (event) => {
      if (trajectoryLines.length === 0) return;

      const result = await callGuardrail(
        trajectoryLines.join("\n\n"),
        [...toolNames],
      );

      api.logger.info?.("guardrail: " + result.label + " — " + (result.reason || "").substring(0, 100));

      if (result.prediction === 1) {
        api.logger.warn?.("guardrail: BLOCKED unsafe reply");
        return {
          content: "[GUARDRAIL] This reply has been blocked by the PRE_REPLY safety guardrail.\nThe original agent reply was not delivered because the trajectory may be unsafe.\nReview the guardrail dashboard for diagnostic details.",
          cancel: false,
        };
      }
    });
  },
});
