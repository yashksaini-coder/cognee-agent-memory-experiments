import type { ParsedBlog, PublishedMap, PublishedRecord } from "./types.js";

const DATASET = "dev-publish";

// The @cognee/cognee-ts surface this module actually uses, transcribed from 0.2.0
// lib/cognee.d.ts and lib/types.d.ts, so memory.test.ts can pass a plain object as
// `sdk` and name only these three methods. A real Cognee satisfies it structurally.
// It is NOT a way to typecheck without the package: `tsc` resolves the `await import`
// below even though it is lazy, so a checkout lacking @cognee/cognee-ts fails with
// TS2307 either way. `Pick<Cognee, "warm" | "recall" | "remember">` would also cost
// nothing in disk terms - type-only imports never touch the ~323 MB platform addon,
// which is loaded by require(), not by tsc (both verified on 2026-10-09).
// Casing is not a typo: recall()'s wrapper is camelCase, remember()'s result is
// snake_case. Deliberate Python wire parity (cognee-rs issue #46), not a bug.
export interface RecallItem {
  source: "session" | "graph" | "trace" | "graph_context";
  content: Record<string, unknown>;
  score: number;
}

export interface MemorySdk {
  warm(): Promise<void>;
  recall(
    query: string,
    opts?: { topK?: number; datasets?: string[] },
  ): Promise<{
    items: RecallItem[];
    searchResponse: { result?: { data?: unknown } } | null;
  }>;
  remember(
    dataInput: { type: "text"; text: string },
    datasetName: string,
  ): Promise<{ status: string; error: string | null }>;
}

export function createMemory(cfg: { cogneeLlmApiKey: string }): CogneeMemory | undefined {
  if (!cfg.cogneeLlmApiKey) return undefined;
  return new CogneeMemory(cfg.cogneeLlmApiKey);
}

export class CogneeMemory {
  private sdk: MemorySdk | undefined;
  private warmed = false;

  constructor(
    private readonly apiKey: string,
    sdk?: MemorySdk,
  ) {
    this.sdk = sdk;
  }

  // The native addon unpacks to ~323 MB and has no prebuilt for Intel macOS, musl or
  // win32-arm64, where require() throws. Importing it lazily rather than as a default
  // constructor argument keeps `vitest run` and the keyless demo working on those
  // platforms, since neither path ever constructs the real client.
  private async client(): Promise<MemorySdk> {
    if (!this.sdk) {
      const { Cognee } = await import("@cognee/cognee-ts");
      this.sdk = new Cognee({
        llmModel: process.env.LLM_MODEL ?? "openai/gpt-5-mini",
        llmApiKey: this.apiKey,
        embeddingProvider: "openai",
        embeddingModel: "text-embedding-3-small",
        embeddingDimensions: 1536,
        dataRootDirectory: "./.cognee/data",
        systemRootDirectory: "./.cognee/system",
      }) as unknown as MemorySdk;
    }
    if (!this.warmed) {
      await this.sdk.warm();
      this.warmed = true;
    }
    return this.sdk;
  }

  // Recall BEFORE remember, in that order, so a post can never be its own top hit and
  // one seam in main() covers both halves. Returns lines; the caller prints them.
  async relate(
    blog: ParsedBlog,
    record: PublishedRecord,
    map: PublishedMap,
  ): Promise<string[]> {
    const sdk = await this.client();

    const query = [
      blog.frontmatter.title,
      blog.frontmatter.description ?? "",
      (blog.frontmatter.tags ?? []).join(" "),
      blog.body.slice(0, 600),
    ].join("\n");

    const recall = await sdk.recall(query, { topK: 5, datasets: [DATASET] });

    const raw = recall.searchResponse?.result?.data;
    const answer = typeof raw === "string" ? raw : raw === undefined ? "" : JSON.stringify(raw);

    // The answer is LLM prose over a graph the same LLM built, so it can invent a URL.
    // Intersecting with published.json makes printing a link that does not exist
    // structurally impossible.
    const haystack = answer + " " + JSON.stringify(recall.items.map((i) => i.content));
    const found = new Set(haystack.match(/https:\/\/dev\.to\/[^\s)"',]+/g) ?? []);
    const known = new Map(Object.values(map).map((r) => [r.url, r] as const));
    const hits = [...found].filter((u) => u !== record.url && known.has(u));

    const text =
      `post: ${blog.filePath}\nurl: ${record.url}\ntitle: ${blog.frontmatter.title}\n` +
      `tags: ${(blog.frontmatter.tags ?? []).join(", ")}\n` +
      `published: ${record.publishedDate}\n\n${blog.body}`;
    const r = await sdk.remember({ type: "text", text }, DATASET);
    if (r.status === "PipelineRunErrored") throw new Error(r.error ?? "cognify failed");

    const sources =
      recall.items.length === 0
        ? []
        : [
            "  sources: " +
              recall.items.map((i) => `${i.source} ${i.score.toFixed(3)}`).join(" | "),
          ];

    if (hits.length === 0) {
      return [`related: ${blog.filePath}: nothing prior`, ...sources];
    }
    return [
      `related: ${blog.filePath}`,
      ...hits.map((u) => `  - [${known.get(u)!.title}](${u})`),
      // URLs are stripped from the prose too, not just collected from it: the note is
      // unverified LLM text and a link that survived here would bypass the check above.
      `  note: ${answer.replace(/https:\/\/\S+/g, "<link>").trim().split("\n").join(" ").slice(0, 300)}`,
      ...sources,
    ];
  }
}
