import { describe, it, expect } from "vitest";
import { LlmConfigError, resolveLlm } from "./llm.js";

// Pure: resolveLlm reads only the env object it is handed. No key, no network, no addon.
describe("resolveLlm", () => {
  it("is off when the default provider has no key", () => {
    expect(resolveLlm({})).toBeUndefined();
  });

  it("keeps the OpenAI defaults the demo always had", () => {
    expect(resolveLlm({ COGNEE_LLM_API_KEY: "sk-test" })?.settings).toMatchObject({
      llmProvider: "openai",
      llmModel: "openai/gpt-5-mini",
      embeddingProvider: "openai",
      embeddingModel: "text-embedding-3-small",
      embeddingDimensions: 1536,
    });
  });

  it("gives anthropic local embeddings and a model that accepts temperature", () => {
    const llm = resolveLlm({ LLM_PROVIDER: "anthropic", ANTHROPIC_API_KEY: "sk-ant-api03-x" });
    expect(llm?.settings).toMatchObject({
      llmModel: "claude-haiku-4-5-20251001",
      llmApiKey: "sk-ant-api03-x",
      embeddingProvider: "ollama",
      embeddingDimensions: 768,
    });
  });

  it("rejects every Claude model probed to refuse temperature, and only those", () => {
    const run = (model: string) => () =>
      resolveLlm({ LLM_PROVIDER: "anthropic", COGNEE_LLM_API_KEY: "sk-ant-api03-x", LLM_MODEL: model });
    for (const m of [
      "claude-haiku-5-5",
      "claude-opus-5",
      "claude-fable-5-1",
      "claude-opus-4-7",
      "claude-opus-4-8",
      "anthropic/claude-haiku-5-5",
    ])
      expect(run(m), m).toThrow(LlmConfigError);
    for (const m of ["claude-sonnet-4-6", "claude-haiku-4-5-20251001"]) expect(run(m), m).not.toThrow();
  });

  it("runs ollama without a key, on the /v1 route, with a placeholder the SDK accepts", () => {
    expect(resolveLlm({ LLM_PROVIDER: "ollama" })?.settings).toMatchObject({
      llmEndpoint: "http://localhost:11434/v1",
      llmApiKey: "not-needed",
    });
  });

  it("needs an endpoint and a model for openai_compatible", () => {
    expect(() => resolveLlm({ LLM_PROVIDER: "openai_compatible", LLM_MODEL: "m" })).toThrow(/LLM_ENDPOINT/);
    expect(() => resolveLlm({ LLM_PROVIDER: "openai_compatible", LLM_ENDPOINT: "http://x/v1" })).toThrow(
      /LLM_MODEL/,
    );
  });

  it("refuses to guess embedding dimensions", () => {
    expect(() => resolveLlm({ LLM_PROVIDER: "ollama", EMBEDDING_MODEL: "some-new-model" })).toThrow(
      /EMBEDDING_DIMENSIONS/,
    );
  });

  it("catches an Anthropic key on the wrong provider, and a user-scoped key", () => {
    expect(() => resolveLlm({ COGNEE_LLM_API_KEY: "sk-ant-api03-x" })).toThrow(/LLM_PROVIDER=anthropic/);
    expect(() => resolveLlm({ LLM_PROVIDER: "anthropic", COGNEE_LLM_API_KEY: "sk-ant-usr-x" })).toThrow(
      /workspace/,
    );
  });

  it("does not turn on just because OPENAI_API_KEY is exported", () => {
    expect(resolveLlm({ OPENAI_API_KEY: "sk-test" })).toBeUndefined();
    expect(resolveLlm({ LLM_PROVIDER: "openai", OPENAI_API_KEY: "sk-test" })).toBeDefined();
  });

  it("never hands the LLM key to an ollama embedding endpoint", () => {
    const llm = resolveLlm({
      LLM_PROVIDER: "anthropic",
      COGNEE_LLM_API_KEY: "sk-ant-api03-SECRET",
      EMBEDDING_ENDPOINT: "https://embeddings.example.com/api/embed",
    });
    expect(llm?.settings.embeddingApiKey).toBe("not-needed");
  });

  it("rejects dimensions that are not a positive integer", () => {
    for (const d of ["abc", "-768", "76.8"])
      expect(() => resolveLlm({ LLM_PROVIDER: "ollama", EMBEDDING_DIMENSIONS: d }), d).toThrow(/positive integer/);
  });

  it("catches a non-Anthropic key on the anthropic provider, and inherited names", () => {
    expect(() => resolveLlm({ LLM_PROVIDER: "anthropic", COGNEE_LLM_API_KEY: "sk-proj-x" })).toThrow(/sk-ant-/);
    expect(() => resolveLlm({ LLM_PROVIDER: "constructor" })).toThrow(/not supported/);
  });

  it("never puts the key in the label", () => {
    const llm = resolveLlm({ LLM_PROVIDER: "anthropic", COGNEE_LLM_API_KEY: "sk-ant-api03-SECRET" });
    expect(llm?.label).not.toContain("SECRET");
  });
});
