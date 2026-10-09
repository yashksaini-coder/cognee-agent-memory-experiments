import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { CogneeMemory } from "./memory.js";
import type { MemorySdk } from "./memory.js";
import type { BlogFrontmatter, ParsedBlog, PublishedMap } from "./types.js";

const FIXTURES = fileURLToPath(new URL("../fixtures/", import.meta.url));
const RESULTS = fileURLToPath(
  new URL("../../../experiments/db_memory/results.json", import.meta.url),
);
const DATASET = "dev-publish";

// Enough YAML for fixtures this file's author also wrote. dev-publish uses gray-matter
// (src/frontmatter.ts:17); vendoring that here would add a dependency to prove nothing.
function parseBlog(filePath: string, raw: string): ParsedBlog {
  const end = raw.indexOf("\n---", 4);
  const head = raw.slice(4, end);
  const body = raw.slice(end + 4).trim();
  const field = (k: string): string | undefined =>
    new RegExp(`^${k}: (.*)$`, "m").exec(head)?.[1]?.trim().replace(/^['"]|['"]$/g, "");
  const tags = field("tags");
  const frontmatter: BlogFrontmatter = {
    title: field("title") ?? "",
    description: field("description"),
    tags: tags ? tags.replace(/^\[|\]$/g, "").split(",").map((t) => t.trim()) : [],
    published: field("published") === "true",
  };
  return { filePath, frontmatter, body, contentHash: createHash("sha256").update(raw, "utf8").digest("hex") };
}

// dev-publish src/frontmatter.ts:42, verbatim.
function normalizeTags(tags: string[] | undefined): string[] {
  if (!tags) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of tags) {
    const tag = raw.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (!tag || seen.has(tag)) continue;
    seen.add(tag);
    out.push(tag);
    if (out.length === 4) break;
  }
  return out;
}

// Ported byte-for-byte from experiments/db_memory/db_demo.py:28-33 so this row's count
// is comparable to results.json. A different tokenizer under the same label is a lie.
const STOP = new Set(
  `a an and are as at be but by for from has have i in is it its my of on or our so
that the their there this to was we were with after still what which two`.split(/\s+/),
);
function words(text: string): Set<string> {
  return new Set((text.toLowerCase().match(/[a-z]+/g) ?? []).filter((w) => !STOP.has(w) && w.length > 2));
}

const map: PublishedMap = JSON.parse(readFileSync(FIXTURES + "published.json", "utf8")) as PublishedMap;
const blogs = readdirSync(FIXTURES + "blogs")
  .filter((n) => n.endsWith(".md"))
  .sort()
  .map((n) => parseBlog(`fixtures/blogs/${n}`, readFileSync(`${FIXTURES}blogs/${n}`, "utf8")));

const fresh = blogs.find((b) => map[b.filePath] === undefined);
if (!fresh) throw new Error("every fixture is already in published.json: nothing to publish");
const archive = blogs.filter((b) => b !== fresh);
const kb = (archive.reduce((n, b) => n + Buffer.byteLength(b.body), 0) / 1024).toFixed(1);

console.log(`corpus: ${archive.length} published posts (${kb} KB), 1 being published`);
console.log(`new post: ${fresh.filePath}`);
console.log(`title: ${fresh.frontmatter.title}\n`);

// Row 1. What data/published.json can retrieve with, today.
const hashHits = archive.filter((b) => map[b.filePath]!.contentHash === fresh.contentHash);
console.log(`contentHash   ${hashHits.length}/${archive.length}`);
console.log("  sha256 of a different file matches nothing. this is the entire retrieval");
console.log("  capability of data/published.json.\n");

// Row 2.
const freshTags = new Set(normalizeTags(fresh.frontmatter.tags));
const tagHits = archive.filter((b) => normalizeTags(b.frontmatter.tags).some((t) => freshTags.has(t)));
console.log(`tag overlap   ${tagHits.length}/${archive.length}   [${[...freshTags].join(" ")}]`);
for (const b of archive) {
  const shared = normalizeTags(b.frontmatter.tags).filter((t) => freshTags.has(t));
  console.log(`  ${shared.length} ${b.filePath}${shared.length ? `  (${shared.join(" ")})` : ""}`);
}
console.log();

// Row 3. The repo's measured finding, re-run on real prose instead of synthetic sessions.
const freshWords = words(fresh.frontmatter.title + " " + fresh.body);
const overlaps = archive.map((b) => ({
  file: b.filePath,
  n: [...words(b.frontmatter.title + " " + b.body)].filter((w) => freshWords.has(w)).length,
}));
const wordHits = overlaps.filter((o) => o.n > 0);
console.log(`word overlap  ${wordHits.length}/${archive.length}`);
console.log(`  (${archive.length - wordHits.length}/${archive.length} prior posts share no content word with this one)`);
for (const o of overlaps) console.log(`  ${o.n} ${o.file}`);
// The same count on the repo's synthetic support sessions, read out of results.json
// rather than retyped, because it points the other way and that is the finding.
// results.json stores the complement (how many phrasings DO share a word), so the
// subtraction is here and not in anybody's prose.
if (existsSync(RESULTS)) {
  const prior = JSON.parse(readFileSync(RESULTS, "utf8")) as {
    complaint_vs_fix: { phrasings: unknown[]; phrasings_sharing_any_word: number };
  };
  const { phrasings, phrasings_sharing_any_word: shared } = prior.complaint_vs_fix;
  console.log(
    `  for contrast, experiments/db_memory/results.json: ${phrasings.length - shared}/${phrasings.length} phrasings`,
  );
  console.log("  of one bug share no content word with the PR that fixed it");
}
console.log();

const apiKey = process.env.COGNEE_LLM_API_KEY ?? "";
if (!apiKey) {
  console.log("cognee rows: skipped (set COGNEE_LLM_API_KEY to run them)");
  console.log(
    'there is no offline cognee mode in @cognee/cognee-ts@0.2.0: embeddingProvider:"mock"',
  );
  console.log(
    "removes embeddings only, and MOCK_LLM needs a crate feature the npm build does not ship.",
  );
} else {
  try {
    await cogneeRows(apiKey, fresh);
  } catch (error) {
    // One line, not a 20-frame stack. Three things land here: no install, a platform
    // with no prebuilt (Intel macOS, musl, win32-arm64 - require() is where that
    // surfaces), and a key the provider rejects on the first LLM call.
    const first = error instanceof Error ? error.message.split("\n")[0] : String(error);
    console.log(`cognee rows: failed: ${first}`);
    process.exitCode = 1;
  }
}

// `fresh` is passed in rather than closed over: the `if (!fresh) throw` narrowing
// above does not survive into a function body.
async function cogneeRows(apiKey: string, fresh: ParsedBlog): Promise<void> {
  // One handle, shared by the product module and row 4, so warm() runs once.
  const { Cognee } = await import("@cognee/cognee-ts");
  const sdk = new Cognee({
    llmModel: process.env.LLM_MODEL ?? "openai/gpt-5-mini",
    llmApiKey: apiKey,
    embeddingProvider: "openai",
    embeddingModel: "text-embedding-3-small",
    embeddingDimensions: 1536,
    dataRootDirectory: "./.cognee/data",
    systemRootDirectory: "./.cognee/system",
  });
  const memory = new CogneeMemory(apiKey, sdk as unknown as MemorySdk);
  const started = performance.now();

  for (const [i, b] of archive.entries()) {
    const t = performance.now();
    await memory.relate(b, map[b.filePath]!, map);
    console.log(`seeding: ${i + 1}/${archive.length} ${b.filePath} ${Math.round(performance.now() - t)} ms`);
  }
  console.log();

  const query = [
    fresh.frontmatter.title,
    fresh.frontmatter.description ?? "",
    (fresh.frontmatter.tags ?? []).join(" "),
    fresh.body.slice(0, 600),
  ].join("\n");

  console.log("cognee as a vector store [search CHUNKS, onlyContext, no LLM]");
  const res = await sdk.search(query, {
    searchType: "CHUNKS",
    datasets: [DATASET],
    topK: 5,
    onlyContext: true,
  });
  if (res.result.kind === "Items") {
    for (const it of res.result.data) console.log(`  ${it.score} ${JSON.stringify(it.payload).slice(0, 180)}`);
  } else {
    console.log(`  unexpected result kind: ${res.result.kind}`);
  }
  console.log();

  // main() would have published it by now; this is the record it would have written.
  const record = {
    articleId: 9999,
    title: fresh.frontmatter.title,
    url: `https://dev.to/example/${fresh.filePath.replace(/^.*\/|\.md$/g, "")}`,
    published: true,
    publishedDate: new Date().toISOString(),
    lastUpdated: new Date().toISOString(),
    contentHash: fresh.contentHash,
  };
  console.log("cognee as a memory layer [recall, GRAPH_COMPLETION]");
  for (const line of await memory.relate(fresh, record, map)) console.log(`  ${line}`);
  console.log(`\ncognee phase: ${Math.round(performance.now() - started)} ms`);
}
