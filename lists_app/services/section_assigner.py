"""
Section assignment: keyword rules (French) from DB first, optional LLM fallback.
New keywords learned from LLM are stored in the DB. All section labels and LLM prompt in French.
"""

import json
import logging
import re
from typing import Optional

from django.conf import settings
from django.db import transaction

from lists_app.models import Section, SectionKeyword
from lists_app.services.llm_client import call_llm

logger = logging.getLogger(__name__)

# Max length for item name sent to LLM
LLM_INPUT_MAX_LENGTH = 200


def _normalize(text: str) -> str:
    """Normalize for matching: strip, lower, collapse spaces."""
    if not text or not isinstance(text, str):
        return ""
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _match_keywords(normalized: str) -> Optional[str]:
    """Return section slug if any keyword matches (longest first for phrases)."""
    if not normalized:
        return None
    keywords = list(
        SectionKeyword.objects.select_related("section").all().order_by("keyword")
    )
    logger.debug(
        "keyword lookup: normalized=%r, keywords_count=%d", normalized, len(keywords)
    )
    # Prefer longer phrases first
    for rec in sorted(keywords, key=lambda r: -len(r.keyword)):
        if rec.keyword in normalized:
            return rec.section.name_slug
    return None


def _call_llm(item_name: str) -> Optional[str]:
    """
    Call LLM with French prompt to classify item into a section.
    Returns section slug or None on failure.
    """
    if not item_name:
        return None
    name = (item_name or "").strip()[:LLM_INPUT_MAX_LENGTH]
    if not name:
        return None
    section_list = list(
        Section.objects.order_by("position").values_list("name_slug", "label_fr")
    )
    sections_fr = ", ".join(f"{slug}={label}" for slug, label in section_list)
    prompt = (
        "Tu es un assistant. Voici la liste des sections d'un supermarché (slug=label): "
        f"{sections_fr}. "
        f"Pour l'article suivant, réponds UNIQUEMENT avec le slug de la section appropriée, rien d'autre. "
        f"Article: « {name} »"
    )
    content = call_llm(prompt, max_tokens=20, timeout=10)
    if content is None:
        return None
    slug = content.strip().split()[0] if content else ""
    logger.debug("LLM response slug=%r", slug)
    if Section.objects.filter(name_slug=slug).exists():
        return slug
    return None


# Max length of pasted text sent to LLM for import normalization
IMPORT_LLM_INPUT_MAX_LENGTH = 4000


def normalize_import_with_llm(raw_text: str) -> list[dict]:
    """
    Call LLM to normalize a pasted grocery list into a JSON array of items.
    Returns list of {"name": str, "quantity": str, "section_slug": str | None}.
    Returns [] if LLM is unavailable or on any error (caller can fall back to client parsing).
    """
    if not (getattr(settings, "LLM_API_KEY", "") or "").strip():
        return []
    text = (raw_text or "").strip()[:IMPORT_LLM_INPUT_MAX_LENGTH]
    if not text:
        return []
    section_list = list(
        Section.objects.order_by("position").values_list("name_slug", "label_fr")
    )
    sections_fr = ", ".join(f"{slug}={label}" for slug, label in section_list)
    valid_slugs = set(slug for slug, _ in section_list)
    prompt = (
        "L'utilisateur a collé une liste de courses en texte libre. Elle peut être désordonnée "
        "(formats variés : « Nom : quantité », « quantité nom », tirets, numéros, etc.). Certaines lignes peuvent contenir des élement à ignorer comme le titre d'un section.\n"
        "Normalise-la en un tableau JSON. Chaque élément doit être un objet avec exactement :\n"
        "- \"name\" : string (nom de l'article normalisé avec une majuscule sans les details autours)\n"
        "- \"quantity\" : string (quantité, peut être \"\" si aucune)\n"
        "- \"section_slug\" : string ou null (un des slugs ci-dessous, ou null si inconnu)\n"
        f"Sections autorisées (slug=label) : {sections_fr}.\n"
        "Réponds UNIQUEMENT par le tableau JSON minifié, sans markdown, sans explication.\n\n"
        "Liste collée par l'utilisateur :\n"
        f"{text}"
    )
    content = call_llm(prompt, max_tokens=1024, timeout=30)
    if content is None:
        return []
    try:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        content = content.replace("\\\\\\", "\\")
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            return []
        result = []
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if name is None:
                continue
            name = str(name).strip()
            if not name:
                continue
            quantity = entry.get("quantity")
            quantity = "" if quantity is None else str(quantity).strip()
            section_slug = entry.get("section_slug")
            if section_slug is not None:
                section_slug = str(section_slug).strip()
                if section_slug not in valid_slugs:
                    section_slug = None
            result.append({
                "name": name,
                "quantity": quantity,
                "section_slug": section_slug,
            })
        logger.info("LLM import normalized count=%d", len(result))
        return result
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("LLM import normalize failed: %s", e)
        return []


@transaction.atomic
def assign_section(item_name: str, default_slug: str = "autre") -> Optional[Section]:
    """
    Assign a section to an item by name. Tries keyword rules (DB) first, then optional LLM.
    When LLM assigns a section, the normalized item name is stored as a keyword for next time.
    Returns a Section instance or None (caller may use default).
    """
    normalized = _normalize(item_name or "")
    logger.debug("assign_section normalized=%r", normalized)

    slug = _match_keywords(normalized)
    if slug:
        try:
            section = Section.objects.get(name_slug=slug)
            logger.info(
                "section assigned: item_name=%r, source=keyword, section=%s",
                item_name,
                section.name_slug,
            )
            return section
        except Section.DoesNotExist:
            pass

    slug = _call_llm(item_name)
    if slug:
        try:
            section = Section.objects.get(name_slug=slug)
            SectionKeyword.objects.get_or_create(
                keyword=normalized, defaults={"section": section}
            )
            logger.info(
                "section assigned: item_name=%r, source=llm, section=%s",
                item_name,
                section.name_slug,
            )
            logger.info(
                "learned keyword: keyword=%r, section=%s",
                normalized,
                section.name_slug,
            )
            return section
        except Section.DoesNotExist:
            pass

    try:
        section = Section.objects.get(name_slug=default_slug)
        logger.info(
            "section assigned: item_name=%r, source=default, section=%s",
            item_name,
            section.name_slug,
        )
        return section
    except Section.DoesNotExist:
        section = Section.objects.order_by("position").first()
        if section:
            logger.info(
                "section assigned: item_name=%r, source=fallback, section=%s",
                item_name,
                section.name_slug,
            )
        return section
