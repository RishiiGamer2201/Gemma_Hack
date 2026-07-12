"""Offline legal-aid directory models and verified snapshot processing."""

from .directory import LegalAidContact, LegalAidFallback, build_delhi_contacts, build_tele_law_fallback

__all__ = ["LegalAidContact", "LegalAidFallback", "build_delhi_contacts", "build_tele_law_fallback"]
