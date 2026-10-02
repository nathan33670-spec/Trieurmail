"""Pré-score local (gratuit) : sert à filtrer et ordonner avant tout appel IA."""
from __future__ import annotations

import re
import time

from ..mail.models import MailHeader

URGENT_RE = re.compile(
    r"\b(urgent|urgence|asap|au plus vite|rapidement|immédiat\w*|deadline|échéance|avant (le|ce|demain|vendredi|lundi)|"
    r"d'ici|relance|rappel|important|action requise|action required|impayé\w*|retard|expir\w*|dernier délai|"
    r"incident|bloqu\w*|signature|à signer|validation|valider)\b",
    re.I,
)
QUESTION_RE = re.compile(r"\?|\b(peux-tu|pourriez-vous|pouvez-vous|could you|can you|merci de)\b", re.I)


def heuristic_priority(h: MailHeader, me: set[str], close_contacts: set[str], now: float | None = None) -> int:
    now = now or time.time()
    score = 35
    if h.is_bulk:
        score -= 25
    to = set(filter(None, h.to_addrs.split(",")))
    cc = set(filter(None, h.cc_addrs.split(",")))
    if me & to:
        score += 12 if len(to) <= 3 else 6
    elif me & cc:
        score += 2
    if h.in_reply_to:
        score += 8
    if h.from_addr in close_contacts:
        score += 15
    if URGENT_RE.search(h.subject):
        score += 15
    elif URGENT_RE.search(h.snippet):
        score += 6
    if QUESTION_RE.search(h.subject) or QUESTION_RE.search(h.snippet):
        score += 6
    if h.high_importance:
        score += 10
    if h.flagged:
        score += 15
    age_days = (now - h.date) / 86400 if h.date else 0
    if age_days > 21:
        score -= 12
    elif age_days > 7:
        score -= 5
    return max(0, min(100, score))


def tier(score: int) -> str:
    if score >= 80:
        return "urgent"
    if score >= 60:
        return "important"
    if score >= 35:
        return "normal"
    return "faible"
