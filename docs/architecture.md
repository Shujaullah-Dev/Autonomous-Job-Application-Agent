## Multi-Source Job Discovery

The AI Job Agent supports multiple external job providers.

### Supported Providers

1. Greenhouse Job Board API
2. Lever Postings API

### Architecture

```text
Greenhouse ─┐
            ├── Provider Adapters
Lever ──────┘
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
             Supabase
```

### Provider Identity

Each imported job maintains:

- source
- source_job_id
- job_url
- canonical_url

### Deduplication

The system uses:

1. Provider-specific identity
2. Canonical URL comparison
3. Company/title/location fingerprint

Potential cross-provider duplicates are skipped
and reported for review.

### Database

Both providers use the existing jobs table.

No separate job table is maintained for each provider.
