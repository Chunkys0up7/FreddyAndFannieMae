import {
  CopilotRuntime,
  copilotRuntimeNextJSAppRouterEndpoint,
  AnthropicAdapter,
  OpenAIAdapter,
} from "@copilotkit/runtime";
import Anthropic from "@anthropic-ai/sdk";
import OpenAI from "openai";
import { NextRequest } from "next/server";

const provider = (process.env.LLM_PROVIDER || "anthropic").toLowerCase();
const agentUrl = process.env.AGENT_URL || "http://localhost:8000/copilotkit";

function buildAdapter() {
  if (provider === "openai") {
    const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    return new OpenAIAdapter({ openai, model: process.env.OPENAI_MODEL || "gpt-4o-mini" });
  }
  const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  return new AnthropicAdapter({
    anthropic,
    model: process.env.ANTHROPIC_MODEL || "claude-sonnet-4-6",
  });
}

const runtime = new CopilotRuntime({
  remoteEndpoints: [{ url: agentUrl }],
});

export const POST = async (req: NextRequest) => {
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime,
    serviceAdapter: buildAdapter(),
    endpoint: "/api/copilotkit",
  });
  return handleRequest(req);
};
