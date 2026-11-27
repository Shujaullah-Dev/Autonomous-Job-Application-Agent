## Multi-Source Job Discovery

The AI Job Agent supports multiple external job providers.

### Supported Providers

Company job boards (public, unauthenticated APIs):

1. Greenhouse Job Board API
2. Lever Postings API
3. Ashby job board API
4. Workable widget API
5. SmartRecruiters postings API

Public feeds that need no company token:

6. Remotive
7. Arbeitnow
8. Jobicy
9. Remote OK
10. Himalayas

### Architecture

```text
Greenhouse ───┐
Lever ────────┤
Ashby ────────┤
Workable ─────┼── Provider Adapters
SmartRecruiters ┤
Remotive ─────┤
Arbeitnow ────┤
Jobicy ───────┤
Remote OK ────┤
Himalayas ────┘
                  |
                  v
           Job Normalization
                  |
                  v
          URL Canonicalization
                  |
                  v
          Duplicate Detection
                  |
                  v
            Job Ingestion
                  |
                  v
               Database
```

### Import flow

`python -m app.scripts.ingest_jobs` builds a `SourceSpec` per requested
account (`backend/app/services/job_sources/catalog.py`). Each source is fetched,
normalized and ingested on its own, so a failed or empty board is reported and
skipped rather than aborting the whole run. `--defaults` uses the curated,
verified catalog; `--max-per-source` keeps a single run bounded because every
source is imported newest first.

### Provider Identity

Each imported job maintains:

- source
- source_job_id
- job_url
- canonical_url

The `source` value is prefixed with the provider (`greenhouse:stripe`,
`lever:spotify`, `ashby:openai`, `workable:huggingface`,
`smartrecruiters:BoschGroup`) or is the feed name (`remotive`, `arbeitnow`,
`jobicy`, `remoteok`, `himalayas`).

### Deduplication

The system uses:

1. Provider-specific identity
2. Canonical URL comparison
3. Company/title/location fingerprint

Potential cross-provider duplicates are skipped
and reported for review.

### Database

All providers use the existing jobs table.

No separate job table is maintained for each provider.
