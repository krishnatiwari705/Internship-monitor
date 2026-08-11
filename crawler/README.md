# Production Internship Crawler

This is the ingestion and matching layer for the Internship Monitor.

## Pipeline

`RSS/search discovery -> Greenhouse/Lever adapters -> normalization -> relevance filter -> profile scoring -> stable deduplication -> new/updated detection -> JSON data -> dashboard`

## Sources

1. **Greenhouse Job Board API** — public GET endpoints; configured with board tokens in `config.json` or `GREENHOUSE_BOARDS`.
2. **Lever public postings** — configured with site names in `config.json` or `LEVER_SITES`.
3. **RSS/search discovery** — broad discovery for opportunities without a configured ATS adapter.

The Greenhouse adapter stores stable job IDs, published/updated timestamps, location, description and the direct application URL. The public Greenhouse GET endpoints do not require authentication. The Lever adapter consumes published postings and hosted/application URLs.

## Freshness and deduplication

- Stable IDs use source + external ID + URL + title.
- `seen.json` records IDs already surfaced.
- `new_jobs.json` contains only newly discovered jobs for the current run.
- Jobs with a changed source `updated` timestamp are marked `updated`.
- Existing `first_seen` timestamps are preserved.

## Matching

The first-pass matcher is configured for the user's profile:

- 2027 B.Tech CSE
- AI / GenAI / RAG / ML
- Python / Java / C++
- FastAPI / Node.js / Express / React
- REST APIs / MongoDB / Docker / Git
- LangChain / LangGraph / Gemini
- Delhi NCR and Remote India

The score is deterministic ranking, not a claim of an LLM evaluation. An LLM/JD parser can be added later behind a GitHub secret without putting credentials in source control.

## GitHub Actions

`.github/workflows/job-crawler.yml` runs hourly and can also be started manually. Scheduled workflows are not guaranteed to start at the exact minute, so this is hourly monitoring rather than real-time streaming.

## Adding ATS boards

Greenhouse:

```json
{"company":"Example","token":"example"}
```

Lever:

```json
{"company":"Example","site":"example"}
```

Do not commit private API keys. The public posting endpoints used here do not require application credentials.
