// LLM + embedding setup for @cognee/cognee-ts 0.2.0, resolved from env in one place so
// demo.ts, memory.ts and dev-publish (via seam.patch) all build the SDK the same way.
//
// Pick a provider with LLM_PROVIDER; every other variable is an optional override:
//
//   LLM_PROVIDER       openai (default) | anthropic | ollama | openai_compatible
//   LLM_MODEL          provider default below
//   LLM_ENDPOINT       required for openai_compatible (Groq, OpenRouter, LM Studio, vLLM)
//   COGNEE_LLM_API_KEY falls back to OPENAI_API_KEY / ANTHROPIC_API_KEY only when
//                      LLM_PROVIDER is set, so an exported OPENAI_API_KEY alone opts nobody in
//   EMBEDDING_PROVIDER openai | ollama (Anthropic has no embedding API, so it gets ollama)
//   EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, EMBEDDING_ENDPOINT, EMBEDDING_API_KEY
//
// Every rule below was checked against the real SDK or API on 2026-10-22; the comment
// next to each says what was observed. Nothing here makes a network call.

export type LlmProviderName = "openai" | "anthropic" | "ollama" | "openai_compatible";
type EmbeddingProviderName = "openai" | "ollama";

interface LlmPreset {
  model: string;
  endpoint?: string;
  keyEnv?: string; // provider-native fallback for COGNEE_LLM_API_KEY, explicit provider only
  needsKey: boolean; // false: memory turns on without a key
  embedding: EmbeddingProviderName;
}

const LLM_PRESETS: Record<LlmProviderName, LlmPreset> = {
  openai: { model: "openai/gpt-5-mini", keyEnv: "OPENAI_API_KEY", needsKey: true, embedding: "openai" },
  anthropic: {
    // Not claude-haiku-5-5: see TEMPERATURE_REJECTED.
    model: "claude-haiku-4-5-20251001",
    keyEnv: "ANTHROPIC_API_KEY",
    needsKey: true,
    embedding: "ollama",
  },
  // cognee-ts talks to Ollama through its OpenAI-style /v1 route: the bare
  // http://localhost:11434 answers 404 (the Python SDK is the other way round).
  // Route verified with qwen3:4b, which works but took 407 s to ingest one sentence;
  // gemma4 fails cognee's entity schema. llama3.2 is the family cognee's Ollama docs
  // recommend - not yet run here.
  ollama: { model: "llama3.2", endpoint: "http://localhost:11434/v1", needsKey: false, embedding: "ollama" },
  openai_compatible: { model: "", needsKey: false, embedding: "ollama" },
};

const EMBEDDING_PRESETS: Record<EmbeddingProviderName, { model: string; endpoint?: string }> = {
  openai: { model: "text-embedding-3-small" },
  ollama: { model: "nomic-embed-text", endpoint: "http://localhost:11434/api/embed" },
};

// A wrong dimension count does not fail at config time; it surfaces later as a vector
// store error, after ingestion has already been paid for. So unknown models must say it.
const KNOWN_DIMENSIONS: Record<string, number> = {
  "text-embedding-3-small": 1536,
  "nomic-embed-text": 768,
};

// cognee-ts 0.2.0 always sends `temperature` (llmTemperature defaults to 0, and null is
// rejected with "expected f64"), and these models answer 400 "`temperature` is
// deprecated for this model". Probed one by one: every claude-*-5*, opus-4-7 and
// opus-4-8 reject it; sonnet-4-6 and haiku-4-5 accept it.
// Matched after a "provider/" prefix too, the form the openai default already uses.
const TEMPERATURE_REJECTED = /(?:^|\/)claude-(?:opus-4-[78]|[a-z]+-5)/;

// ollama and openai_compatible still refuse an empty key ("llm_api_key must be
// configured"), even though the server ignores it.
const PLACEHOLDER_KEY = "not-needed";

export class LlmConfigError extends Error {}

export interface LlmSetup {
  settings: Record<string, unknown>; // the Cognee constructor argument
  label: string; // safe to log: never contains a key
}

// undefined = memory off (the provider needs a key and none is set). Throws
// LlmConfigError when the config is present but cannot work.
export function resolveLlm(env: NodeJS.ProcessEnv = process.env): LlmSetup | undefined {
  const provider = (env.LLM_PROVIDER || "openai") as LlmProviderName;
  if (!Object.hasOwn(LLM_PRESETS, provider)) {
    throw new LlmConfigError(
      `LLM_PROVIDER=${provider} is not supported; use one of ${Object.keys(LLM_PRESETS).join(", ")}`,
    );
  }
  const preset = LLM_PRESETS[provider];

  const nativeKey = env.LLM_PROVIDER && preset.keyEnv ? env[preset.keyEnv] : undefined;
  const key = env.COGNEE_LLM_API_KEY || nativeKey || "";
  if (!key && preset.needsKey) return undefined;
  checkKeyMatchesProvider(key, provider);

  const model = env.LLM_MODEL || preset.model;
  const endpoint = env.LLM_ENDPOINT || preset.endpoint;
  if (!model) throw new LlmConfigError(`LLM_PROVIDER=${provider} needs LLM_MODEL`);
  if (!endpoint && provider === "openai_compatible") {
    throw new LlmConfigError("LLM_PROVIDER=openai_compatible needs LLM_ENDPOINT, e.g. http://localhost:1234/v1");
  }
  if (provider === "anthropic" && TEMPERATURE_REJECTED.test(model)) {
    throw new LlmConfigError(
      `${model} rejects the temperature @cognee/cognee-ts 0.2.0 always sends; ` +
        `use ${preset.model} or claude-sonnet-4-6`,
    );
  }

  const embeddingProvider = (env.EMBEDDING_PROVIDER || preset.embedding) as EmbeddingProviderName;
  if (!Object.hasOwn(EMBEDDING_PRESETS, embeddingProvider)) {
    throw new LlmConfigError(`EMBEDDING_PROVIDER=${embeddingProvider} is not supported; use openai or ollama`);
  }
  const embeddingPreset = EMBEDDING_PRESETS[embeddingProvider];
  const embeddingModel = env.EMBEDDING_MODEL || embeddingPreset.model;
  const dimensions = env.EMBEDDING_DIMENSIONS ? Number(env.EMBEDDING_DIMENSIONS) : KNOWN_DIMENSIONS[embeddingModel];
  if (dimensions === undefined) {
    throw new LlmConfigError(`unknown dimensions for ${embeddingModel}; set EMBEDDING_DIMENSIONS`);
  }
  if (!Number.isInteger(dimensions) || dimensions <= 0) {
    throw new LlmConfigError(`EMBEDDING_DIMENSIONS=${env.EMBEDDING_DIMENSIONS} is not a positive integer`);
  }
  const embeddingEndpoint = env.EMBEDDING_ENDPOINT || embeddingPreset.endpoint;
  // The SDK falls back to the LLM key for embeddings, which is only right when the
  // same OpenAI account serves both. Ollama always gets its own value, so a Claude key
  // is never sent to EMBEDDING_ENDPOINT, which may be a remote host.
  const embeddingKey =
    env.EMBEDDING_API_KEY ||
    (embeddingProvider === "ollama" ? PLACEHOLDER_KEY : undefined) ||
    (provider !== "openai" ? env.OPENAI_API_KEY : undefined);
  if (embeddingProvider === "openai" && provider !== "openai" && !embeddingKey) {
    throw new LlmConfigError("EMBEDDING_PROVIDER=openai needs EMBEDDING_API_KEY or OPENAI_API_KEY");
  }

  const settings: Record<string, unknown> = {
    llmProvider: provider,
    llmModel: model,
    llmApiKey: key || PLACEHOLDER_KEY,
    llmEndpoint: endpoint,
    embeddingProvider,
    embeddingModel,
    embeddingDimensions: dimensions,
    embeddingEndpoint,
    embeddingApiKey: embeddingKey,
    dataRootDirectory: "./.cognee/data",
    systemRootDirectory: "./.cognee/system",
    // The SDK's default is sqlite:./cognee.db, relative to the cwd, which leaves the
    // metadata store outside .cognee/ and out of step with it when .cognee/ is cleared.
    relationalDbUrl: "sqlite:./.cognee/cognee.db?mode=rwc",
  };
  // Dropped rather than sent as undefined, so the SDK keeps its own default.
  for (const k of Object.keys(settings)) if (settings[k] === undefined) delete settings[k];

  const at = (url?: string) => (url ? ` @ ${url}` : "");
  return {
    settings,
    label:
      `llm ${provider}/${model}${at(endpoint)} · ` +
      `embeddings ${embeddingProvider}/${embeddingModel} ${dimensions}d${at(embeddingEndpoint)}`,
  };
}

// Both mistakes below were made for real and cost a full SDK warm-up to surface as a
// bare "Authentication failed". Prefixes only: the key itself is never echoed.
function checkKeyMatchesProvider(key: string, provider: LlmProviderName): void {
  if (key.startsWith("sk-ant-") && provider !== "anthropic") {
    throw new LlmConfigError("that is an Anthropic key: set LLM_PROVIDER=anthropic");
  }
  if (provider === "anthropic" && key && !key.startsWith("sk-ant-")) {
    throw new LlmConfigError("LLM_PROVIDER=anthropic needs an sk-ant- key; COGNEE_LLM_API_KEY holds another kind");
  }
  if (key.startsWith("sk-ant-usr-")) {
    // Anthropic answers 400 "This API key is not scoped to a workspace", which needs an
    // anthropic-workspace-id header the SDK cannot send.
    throw new LlmConfigError("sk-ant-usr- keys are not workspace-scoped; create an sk-ant-api03- key");
  }
}
