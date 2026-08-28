"""Motore di compatibilita' fra curriculum e offerte di lavoro."""
from . import llm
from .cv_parser import CVParseError, CVProfile, build_profile, extract_text
from .engine import JobView, MatchResult, score_job
from .text import IdfIndex

__all__ = [
    "CVParseError",
    "CVProfile",
    "IdfIndex",
    "JobView",
    "MatchResult",
    "build_profile",
    "extract_text",
    "llm",
    "score_job",
]
