"""Curated public job sources used for a broad default import.

Every board below answered with at least one published listing when the
catalog was checked, so `--defaults` produces current results rather than a
wall of 404s. Boards are public, unauthenticated JSON endpoints.
"""

from dataclasses import dataclass

import httpx

from app.services.job_sources.arbeitnow import ArbeitnowSource
from app.services.job_sources.ashby import AshbySource
from app.services.job_sources.greenhouse import GreenhouseSource
from app.services.job_sources.himalayas import HimalayasSource
from app.services.job_sources.jobicy import JobicySource
from app.services.job_sources.lever import LeverSource
from app.services.job_sources.remoteok import RemoteOkSource
from app.services.job_sources.remotive import RemotiveSource
from app.services.job_sources.smartrecruiters import (
    SmartRecruitersSource,
)
from app.services.job_sources.workable import WorkableSource


@dataclass(frozen=True)
class SourceSpec:
    """One provider account, or one public feed, to import."""

    provider: str
    identifier: str
    company_name: str | None = None

    @property
    def label(self) -> str:
        if self.company_name:
            return f"{self.provider}: {self.company_name}"

        return f"{self.provider}: {self.identifier}"


SOURCES = {
    "greenhouse": GreenhouseSource,
    "lever": LeverSource,
    "ashby": AshbySource,
    "workable": WorkableSource,
    "smartrecruiters": SmartRecruitersSource,
    "remotive": RemotiveSource,
    "arbeitnow": ArbeitnowSource,
    "jobicy": JobicySource,
    "remoteok": RemoteOkSource,
    "himalayas": HimalayasSource,
}

# Public feeds that need no company token.
AGGREGATOR_PROVIDERS = (
    "remotive",
    "arbeitnow",
    "jobicy",
    "remoteok",
    "himalayas",
)

GREENHOUSE_BOARDS = (
    "stripe",
    "airbnb",
    "gitlab",
    "datadog",
    "figma",
    "discord",
    "reddit",
    "coinbase",
    "robinhood",
    "dropbox",
    "instacart",
    "pinterest",
    "samsara",
    "cloudflare",
    "twilio",
    "asana",
    "affirm",
    "flexport",
)

LEVER_SITES = (
    ("spotify", "Spotify"),
    ("palantir", "Palantir"),
)

ASHBY_BOARDS = (
    ("openai", "OpenAI"),
    ("sierra", "Sierra"),
    ("plaid", "Plaid"),
    ("ramp", "Ramp"),
    ("notion", "Notion"),
    ("cohere", "Cohere"),
    ("cursor", "Cursor"),
    ("linear", "Linear"),
    ("vanta", "Vanta"),
    ("replit", "Replit"),
    ("warp", "Warp"),
    ("posthog", "PostHog"),
    ("zapier", "Zapier"),
    ("nabla", "Nabla"),
)

WORKABLE_ACCOUNTS = (
    ("huggingface", "Hugging Face"),
)

SMARTRECRUITERS_COMPANIES = (
    ("BoschGroup", "Bosch Group"),
)


def build_source(
    client: httpx.Client,
    provider: str,
):
    """Create the adapter for a provider key."""

    factory = SOURCES.get(provider.casefold())

    if factory is None:
        raise KeyError(f"Unknown job provider: {provider}")

    return factory(client)


def default_sources() -> list[SourceSpec]:
    """The broad, verified source set behind `--defaults`."""

    specs = [
        SourceSpec("greenhouse", board)
        for board in GREENHOUSE_BOARDS
    ]

    specs.extend(
        SourceSpec("lever", site, company)
        for site, company in LEVER_SITES
    )

    specs.extend(
        SourceSpec("ashby", board, company)
        for board, company in ASHBY_BOARDS
    )

    specs.extend(
        SourceSpec("workable", site, company)
        for site, company in WORKABLE_ACCOUNTS
    )

    specs.extend(
        SourceSpec("smartrecruiters", company_id, company)
        for company_id, company in SMARTRECRUITERS_COMPANIES
    )

    specs.extend(
        SourceSpec(provider, "latest")
        for provider in AGGREGATOR_PROVIDERS
    )

    return specs
