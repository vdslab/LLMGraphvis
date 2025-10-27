# GEMINI integration notes

## Purpose

This document provides operational and integration notes for using the GEMINI LLM (or related configuration) with the LLMGraph-vis system. It is intended as an internal reference for maintainers and operators rather than a Docusaurus site page.

## Project Overview

GEMINI is one of the LLM providers that can be used by the Backend to fulfill natural-language driven requests. This document describes how GEMINI is integrated, recommended practices, and where to update public-facing documentation when the behavior changes.

## Architecture & Major Components (where GEMINI fits)

- **Backend (API Service)**: Proxies requests to GEMINI when GEMINI is selected as the provider. Responsible for prompt construction, response parsing, and tool call orchestration.
- **NetworkXMCP**: Tool service for graph calculations (centrality, layout). The Backend may combine GEMINI responses with tool outputs.
- **Database (PostgreSQL)**: Stores chat history, graph data, cached calculation results, and optionally LLM call metadata (for debugging/traceability).

## Integration Patterns

- Keep prompt templates separate from code where possible. Store canonical prompt examples and explanation text in `specification/` when they affect user-facing behavior.
- Centralize provider selection and credentials in environment configuration. Never hard-code GEMINI keys in the repo.
- When GEMINI returns structured tool-calling instructions, validate inputs server-side before invoking tools (defensive programming).

## Developer Workflows (quick reference)

- **Install dependencies:** `yarn` (frontend) and Python env for backend services
- **Run locally:** Start frontend with `yarn start`. Start backend/NetworkXMCP using the repository's service run scripts.
- **Switch LLM provider:** Configure environment variables and provider flags used by the Backend. Check prompt templates in `specification/` if behavior changes should be documented.

## Operational Notes

- Use secrets management for API keys. Do not commit keys or credentials to source control.
- Log minimal LLM metadata for debugging (request id, model name, sanitized prompt) and avoid storing PII in logs.
- Implement timeouts and retries for external LLM calls to avoid blocking user requests.

## Docs-editing guidance

注意: Docusaurusのドキュメント（サイトに公開される仕様ページ）を編集する場合は、必ずNextバージョンである`specification/`ディレクトリを編集してください。名前に`_versioned_docs/`を含むディレクトリ（例:`specification_versioned_docs/`や`versioned_docs/`）は過去版のドキュメントを格納するためのものであり、編集しないでください。`build/`（ビルド済みファイル）も直接編集しないでください。

補足: `GEMINI.md`と`.github/copilot-instructions.md`はリポジトリ内の補助文書（運用メモやローカル参照用）です。Docusaurus上の仕様ページを更新したい場合は、必ず`specification/`を編集してください。

## References

- `specification/README.md` — Where to make public spec changes
- `.github/copilot-instructions.md` — Contributor/editor guidance

(This file intentionally minimal — expand with GEMINI-specific instructions as needed.)