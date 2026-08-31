"""Registro dei provider e riconoscimento automatico degli URL.

Aggiungere una fonte nuova significa scrivere una sottoclasse di `BaseProvider`
e inserirla in `PROVIDERS`: comparira' da sola nell'interfaccia e nel
riconoscimento automatico degli URL incollati dall'utente.
"""
from __future__ import annotations

from typing import Any

import httpx

from .aggregators import (
    AdzunaProvider,
    ArbeitnowProvider,
    JobicyProvider,
    RemoteOkProvider,
    RemotiveProvider,
    TheMuseProvider,
)
from .ats import (
    AshbyProvider,
    GreenhouseProvider,
    RecruiteeProvider,
    SmartRecruitersProvider,
    WorkableProvider,
    WorkdayProvider,
)
from .base import BaseProvider, JobPosting, ProviderError, SearchSpec
from .linkedin import LinkedInProvider

# L'ordine conta per il riconoscimento degli URL: i piu' specifici per primi.
PROVIDERS: list[type[BaseProvider]] = [
    GreenhouseProvider,
    AshbyProvider,
    SmartRecruitersProvider,
    WorkdayProvider,
    WorkableProvider,
    RecruiteeProvider,
    LinkedInProvider,
    AdzunaProvider,
    TheMuseProvider,
    ArbeitnowProvider,
    RemotiveProvider,
    RemoteOkProvider,
    JobicyProvider,
]

BY_KIND: dict[str, type[BaseProvider]] = {p.kind: p for p in PROVIDERS}


def catalogue() -> list[dict[str, Any]]:
    """Descrizione dei provider disponibili, per la pagina "Aggiungi fonte"."""
    return [
        {
            "kind": p.kind,
            "label": p.label,
            "description": p.description,
            "needs_credentials": p.needs_credentials,
            "supports_query": p.supports_query,
            "default_interval": p.default_interval,
            "url_example": p.url_example,
            "config_fields": p.config_fields,
        }
        for p in PROVIDERS
    ]


def detect_from_url(url: str) -> tuple[type[BaseProvider], dict[str, Any]] | None:
    """Riconosce a quale provider appartiene un URL incollato dall'utente.

    E' il meccanismo dietro "aggiungi fonte incollando il link": l'URL viene
    tradotto nella famiglia di API corrispondente e nei suoi parametri.
    """
    url = (url or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    for provider in PROVIDERS:
        try:
            config = provider.detect(url)
        except Exception:
            config = None
        if config is not None:
            return provider, config
    return None


def build(kind: str, config: dict[str, Any], http: httpx.AsyncClient) -> BaseProvider:
    cls = BY_KIND.get(kind)
    if cls is None:
        raise ProviderError(f"provider sconosciuto: {kind}")
    return cls(config, http)


__all__ = [
    "PROVIDERS",
    "BY_KIND",
    "BaseProvider",
    "JobPosting",
    "ProviderError",
    "SearchSpec",
    "build",
    "catalogue",
    "detect_from_url",
]
