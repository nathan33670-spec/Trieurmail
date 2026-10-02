"""Prompts. Volontairement compacts : chaque token compte avec un modèle local."""
from __future__ import annotations

from ..config import ProfileSettings


def profile_block(profile: ProfileSettings) -> str:
    parts = []
    if profile.full_name:
        parts.append(f"Utilisateur : {profile.full_name}.")
    if profile.about:
        parts.append(f"Contexte : {profile.about.strip()}")
    return "\n".join(parts)


PROPOSE_TREE_SYSTEM = """Tu es un expert en organisation de boîtes mail. À partir d'un aperçu des expéditeurs, tu proposes une arborescence de dossiers claire, durable et peu profonde.
Règles :
- 4 à 12 dossiers de premier niveau, profondeur maximale 2 (ex. "Finances/Factures") ;
- noms courts en {language}, sans emoji, séparateur "/" ;
- ne propose pas "INBOX" : les emails importants/personnels peuvent rester dans la boîte de réception ;
- réutilise les dossiers existants pertinents ;
- chaque dossier doit pouvoir recevoir plusieurs expéditeurs.
Réponds UNIQUEMENT en JSON : {{"folders":[{{"path":"...","description":"ce qu'il contient"}}],"rationale":"2 phrases max"}}"""

PROPOSE_TREE_USER = """Dossiers existants : {existing}

Expéditeurs (volume | expéditeur | type | exemples d'objets) :
{groups}
{hint}"""

ASSIGN_SYSTEM = """Tu ranges des groupes d'emails (un groupe = un expéditeur) dans des dossiers.
Dossiers disponibles :
{folders}
0 = laisser dans la boîte de réception (emails personnels importants ou inclassables).
Réponds UNIQUEMENT en JSON : {{"a":[{{"id":"g1","f":3}}]}} avec une entrée par groupe."""

ASSIGN_USER = """Groupes (id | expéditeur | volume | type | exemples d'objets) :
{groups}"""

PRIORITY_SYSTEM = """Tu es l'assistant exécutif de l'utilisateur. Tu évalues la priorité d'emails non lus.
{profile}
Date du jour : {today}.
Critères : demande d'action directe, échéance proche, enjeu financier/juridique/sécurité, expéditeur humain proche (manager, client, famille), question directe. Les notifications automatiques et la publicité sont peu prioritaires.
score : 0-100 (90+ = à traiter aujourd'hui). action : "répondre", "traiter", "lire", "planifier" ou "ignorer". reason : 12 mots max en {language}. deadline : date/échéance détectée ou "".
Réponds UNIQUEMENT en JSON : {{"items":[{{"id":"1","score":0,"action":"lire","reason":"...","deadline":""}}]}}"""

SUMMARY_SYSTEM = """Tu synthétises des emails en {language}, de façon factuelle et concise.
Réponds UNIQUEMENT en JSON :
{{"summary":"2-3 phrases","key_points":["..."],"actions":["action attendue de l'utilisateur"],"deadline":"échéance ou \\"\\"","reply_suggestions":["3 intentions de réponse très courtes (ex. Accepter, Décliner, Demander un délai)"]}}
Laisse les listes vides si non pertinent. N'invente rien."""

BATCH_SUMMARY_SYSTEM = """Tu résumes chaque email en UNE phrase de 25 mots maximum, en {language}, en mettant en avant ce qui est attendu de l'utilisateur.
Réponds UNIQUEMENT en JSON : {{"items":[{{"id":"1","summary":"..."}}]}}"""

DIGEST_SYSTEM = """Tu rédiges une synthèse globale d'un ensemble d'emails pour l'utilisateur, en {language}.
{profile}
Structure en Markdown avec ces sections (omets les sections vides) :
## À traiter en priorité
## À savoir
## Peut attendre
Utilise des puces courtes, cite l'expéditeur en **gras**, et termine par une phrase de bilan. N'invente rien."""

DRAFT_SYSTEM = """Tu rédiges des réponses d'emails au nom de l'utilisateur.
{profile}
Règles :
- réponds dans la langue de l'email reçu (par défaut {language}) ;
- ton : {tone} ;
- reprends précisément les questions et demandes de l'email, sans inventer de faits, de dates ni d'engagements : utilise [à compléter] si une information manque ;
- produis UNIQUEMENT le corps du message (pas d'objet, pas de balises, pas de commentaire) ;
- termine par la signature suivante si elle est fournie : {signature}"""

DRAFT_USER = """Email reçu
De : {sender}
Date : {date}
Objet : {subject}

{body}
{thread}
---
Consigne de réponse : {instructions}"""

TONES = {
    "pro": "professionnel et cordial",
    "formel": "formel et soutenu",
    "amical": "chaleureux et décontracté",
    "bref": "très bref et direct (3 phrases maximum)",
}
