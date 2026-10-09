---
title: "A 300-token prompt beat a 113k-token one"
description: "Bigger context windows have not removed the need for retrieval, and the benchmarks show why."
tags: [ai, llm, benchmarks, context]
published: true
---

# M6: A 300-token prompt beat a 113k-token one


![Long-context models lose 30-60% on LongMemEval, focused 300-token prompts beat 113k-token prompts, and BEAM scores fall from 0.24-0.28 at 128k to 0.10-0.13 at 10M.](../figures/m6-context-rot.png)

## LinkedIn

Bigger context windows haven't removed the need for retrieval. The benchmarks show why.

From Cognee's benchmarks guide:
• On LongMemEval, long-context LLMs "lose roughly 30-60% of their performance" when they have to find information in a 115k-token history.
• On context rot: "focused prompts of around 300 tokens outperformed full 113k-token prompts."
• On BEAM, long-context models score 0.24–0.28 on the shortest tier and 0.10–0.13 at 10M tokens, and scores already fall at 1M, before the history exceeds the window.

So a model that fits all the text doesn't necessarily use all of it well. Selecting the right 300 tokens is the memory system's job.

## X

Long-context models lose ~30–60% on LongMemEval when the answer is buried in 115k tokens.

Focused ~300-token prompts beat full 113k-token ones.

Fitting the history isn't the same as using it.

## Source

- [AI Memory Benchmarks: The Complete Guide](https://www.cognee.ai/ai-memory-benchmarks), Cognee, 1 Sep 2026
