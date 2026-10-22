import { createHash } from "node:crypto";
import { LlmConfigError, resolveLlm } from "./llm.js";
import type { ParsedBlog, PublishedMap, PublishedRecord } from "./types.js";

// One dataset per post, not one for the archive. In 0.2.0 a dataset ingests once: the
// second remember() into it returns PipelineRunCompleted in ~2 ms having stored
// nothing, and add()+cognify() says so outright ("alreadyCompleted": true, 0 chunks).
// Seeding five posts into one dataset kept only the first (verified 2026-10-22).
// Re-publishing a post maps to the same dataset and is skipped, so edits are not
// re-ingested - the same limit the README already lists under update().
export const DATASET_PREFIX = "dev-publish-";
// Readable slug of the whole path plus a hash of it: with ingest-once datasets a name
// collision (blogs/a/intro.md vs blogs/b/intro.md, or two non-ASCII names) would make the
// second post a silent no-op.
export function datasetFor(filePath: string): string {
  const slug = filePath.toLowerCase().replace(/\.mdx?$/, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${DATASET_PREFIX}${slug.slice(-40)}-${createHash("sha256").update(filePath).digest("hex").slice(0, 8)}`;
}

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

// dev-publish's config.ts reads COGNEE_LLM_API_KEY; everything else about the provider
// comes from env through llm.ts. The memory step is advisory, so a config that cannot
// work turns it off with one warning instead of throwing out of main() before anything
// is published.
export function createMemory(
  cfg: { cogneeLlmApiKey: string },
  env: NodeJS.ProcessEnv = process.env,
): CogneeMemory | undefined {
  try {
    const llm = resolveLlm({ ...env, COGNEE_LLM_API_KEY: cfg.cogneeLlmApiKey || env.COGNEE_LLM_API_KEY });
    return llm && new CogneeMemory(llm.settings);
  } catch (error) {
    const why = error instanceof LlmConfigError ? error.message : `unexpected: ${String(error)}`;
    console.warn(`memory off: ${why}`);
    return undefined;
  }
}

export class CogneeMemory {
  private sdk: MemorySdk | undefined;
  private warmed = false;

  constructor(
    private readonly settings: Record<string, unknown>,
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
      this.sdk = new Cognee(this.settings) as unknown as MemorySdk;
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

    // Asked as a question that names the url. Handed the bare post, GRAPH_COMPLETION
    // summarised it back - it even quoted a prior post's numbers - but prose carries no
    // url, so the strict published.json intersection below found nothing (2026-10-22).
    // Every remembered post has a `url:` line (see `text` below) for it to quote.
    const query = [
      "Which earlier posts cover the same ground as the new post below? " +
        "List the url of each one; answer 'none' if there is none.\n",
      blog.frontmatter.title,
      blog.frontmatter.description ?? "",
      (blog.frontmatter.tags ?? []).join(" "),
      blog.body.slice(0, 600),
    ].join("\n");

    // No `datasets` filter. In 0.2.0 the dataset-name filter needs a
    // user_id that CogneeRecallOptions has no field for (CogneeSearchOptions does:
    // `userId`), so recall() rejects it with "dataset name filter requires
    // SearchRequest.user_id to identify the owner" before any network call. Verified
    // 2026-10-19 on 0.2.0: the same call without `datasets` reaches the LLM instead.
    // Harmless here - remember() below is the only writer and only ever writes
    // dev-publish-* datasets, so an unfiltered graph search has nothing else to find.
    const recall = await sdk.recall(query, { topK: 5 });

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
    const r = await sdk.remember({ type: "text", text }, datasetFor(blog.filePath));
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
