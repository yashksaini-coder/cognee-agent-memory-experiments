import { describe, it, expect } from "vitest";
import { CogneeMemory, createMemory } from "./memory.js";
import type { MemorySdk } from "./memory.js";
import type { ParsedBlog, PublishedMap, PublishedRecord } from "./types.js";

// Hand-rolled dependency injection, the fakeFetch pattern from dev-publish
// src/devto.test.ts:10-26. No key, no network, no native addon.
function fakeSdk(
  answer: string,
  items: unknown[] = [],
  status = "PipelineRunCompleted",
  error: string | null = null,
): MemorySdk & { calls: string[] } {
  const calls: string[] = [];
  return {
    calls,
    warm: async () => {
      calls.push("warm");
    },
    recall: async () => {
      calls.push("recall");
      return { items, searchResponse: { result: { kind: "Text", data: answer } } };
    },
    remember: async () => {
      calls.push("remember");
      return { status, error };
    },
  } as unknown as MemorySdk & { calls: string[] };
}

const record: PublishedRecord = {
  articleId: 7,
  title: "The New One",
  url: "https://dev.to/example/the-new-one",
  published: true,
  publishedDate: "2026-10-08T09:00:00.000Z",
  lastUpdated: "2026-10-08T09:00:00.000Z",
  contentHash: "a".repeat(64),
};

const blog: ParsedBlog = {
  filePath: "blogs/the-new-one.md",
  frontmatter: { title: "The New One", description: "d", tags: ["ai"] },
  body: "body text",
  contentHash: "a".repeat(64),
};

const map: PublishedMap = {
  "blogs/the-new-one.md": record,
  "blogs/real-one.md": { ...record, articleId: 1, title: "Real One", url: "https://dev.to/example/real-one" },
};

describe("CogneeMemory.relate", () => {
  it("recalls before it remembers", async () => {
    const sdk = fakeSdk("nothing here");
    await new CogneeMemory("key", sdk).relate(blog, record, map);
    expect(sdk.calls).toEqual(["warm", "recall", "remember"]);
  });

  it("drops a dev.to url that is not in published.json", async () => {
    const sdk = fakeSdk(
      "see https://dev.to/example/real-one and https://dev.to/example/hallucinated",
    );
    const lines = (await new CogneeMemory("key", sdk).relate(blog, record, map)).join("\n");
    expect(lines).toContain("https://dev.to/example/real-one");
    expect(lines).not.toContain("hallucinated");
  });

  it("never links the post being published to itself", async () => {
    const sdk = fakeSdk(`the closest match is ${record.url}`);
    const lines = await new CogneeMemory("key", sdk).relate(blog, record, map);
    expect(lines).toEqual(["related: blogs/the-new-one.md: nothing prior"]);
  });

  it("throws when cognify errors", async () => {
    const sdk = fakeSdk("", [], "PipelineRunErrored", "boom");
    await expect(new CogneeMemory("key", sdk).relate(blog, record, map)).rejects.toThrow(/boom/);
  });
});

describe("createMemory", () => {
  it("returns undefined when no key is configured", () => {
    expect(createMemory({ cogneeLlmApiKey: "" })).toBeUndefined();
  });
});
