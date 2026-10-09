// Copied verbatim from yashksaini-coder/dev-publish src/types.ts (lines 1-28) at
// 8b42526. Kept in sync by hand; this directory is a standalone demo, not a checkout.
export interface BlogFrontmatter {
  title: string;
  description?: string;
  tags?: string[];
  cover_image?: string;
  canonical_url?: string;
  series?: string;
  published?: boolean;
}

export interface ParsedBlog {
  filePath: string;
  frontmatter: BlogFrontmatter;
  body: string;
  contentHash: string;
}

export interface PublishedRecord {
  articleId: number;
  title: string;
  url: string;
  published: boolean;
  publishedDate: string;
  lastUpdated: string;
  contentHash: string;
}

export type PublishedMap = Record<string, PublishedRecord>;
