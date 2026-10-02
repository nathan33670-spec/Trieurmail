"""Faux serveur compatible OpenAI, déterministe, pour les tests et les démos.

    python tests/fake_llm.py 8799   # puis base_url = http://127.0.0.1:8799/v1
"""
from __future__ import annotations

import json
import re
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

FOLDERS = [
    {"path": "Travail/Équipe", "description": "Collègues, réunions, revues"},
    {"path": "Travail/Outils", "description": "GitHub, Jira, notifications techniques"},
    {"path": "Finances/Factures", "description": "Électricité, téléphone, charges"},
    {"path": "Finances/Banque", "description": "Relevés et alertes bancaires"},
    {"path": "Administratif", "description": "Impôts, juridique, santé"},
    {"path": "Achats & Voyages", "description": "Commandes, billets, réservations"},
    {"path": "Newsletters", "description": "Actualités, offres, réseaux sociaux"},
]
KEYWORDS = [
    (1, ("acme-corp.fr",)), (2, ("github", "jira", "atlassian")), (3, ("edf", "free", "immo")),
    (4, ("bnp",)), (5, ("dgfip", "avocat", "doctolib", "mutuelle")), (6, ("amazon", "sncf", "airbnb")),
    (7, ("linkedin", "monde", "jungle", "decathlon")),
]


def respond(system: str, user: str) -> str:
    if "arborescence" in system:
        return json.dumps({"folders": FOLDERS, "rationale": "Séparation travail / finances / vie perso."})
    if "ranges des groupes" in system:
        out = []
        for line in user.splitlines():
            m = re.match(r"(g\d+) \| (.*)", line)
            if m:
                f = next((i for i, kws in KEYWORDS if any(k in m.group(2).lower() for k in kws)), 0)
                out.append({"id": m.group(1), "f": f})
        return json.dumps({"a": out})
    if "évalues la priorité" in system:
        items = []
        for m in re.finditer(r"\[(\d+)\] De: (.*?)\| Objet: (.*)", user):
            text = m.group(3).lower()
            score = 92 if "urgent" in text else 75 if re.search(r"valid|signature|revue|budget", text) else 45
            items.append({"id": m.group(1), "score": score, "action": "répondre" if score > 70 else "lire",
                          "reason": "Demande d'action directe" if score > 70 else "Information", "deadline": ""})
        return json.dumps({"items": items})
    if "UNE phrase" in system:
        items = [{"id": m.group(1), "summary": f"Résumé de « {m.group(2).strip()[:40]} »."}
                 for m in re.finditer(r"\[(\d+)\] De: .*?\| Objet: (.*)", user)]
        return json.dumps({"items": items})
    if "synthétises" in system:
        return "```json\n" + json.dumps({
            "summary": "L'expéditeur demande une validation rapide.", "key_points": ["Point clé 1"],
            "actions": ["Valider avant vendredi"], "deadline": "vendredi",
            "reply_suggestions": ["Accepter", "Demander un délai", "Décliner"],
        }, ensure_ascii=False) + "\n```"
    if "synthèse globale" in system:
        return "## À traiter en priorité\n- **Thomas** : incident en production.\n\n## À savoir\n- Factures disponibles.\n\nBilan : journée chargée."
    if "rédiges des réponses" in system:
        return "<think>raisonnement caché</think>Bonjour,\n\nMerci pour votre message, je reviens vers vous rapidement.\n\nBien cordialement,\nCamille"
    return "OK"


def make_app() -> FastAPI:
    app = FastAPI()
    app.state.calls = 0

    @app.get("/v1/models")
    async def models():
        return {"data": [{"id": "fake-small"}, {"id": "fake-large"}]}

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        body = await request.json()
        app.state.calls += 1
        msgs = body["messages"]
        system = next((m["content"] for m in msgs if m["role"] == "system"), "")
        user = "\n".join(m["content"] for m in msgs if m["role"] == "user")
        text = respond(system, user)
        if body.get("stream"):
            async def gen():
                for i in range(0, len(text), 12):
                    yield "data: " + json.dumps({"choices": [{"delta": {"content": text[i:i + 12]}}]}) + "\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(gen(), media_type="text/event-stream")
        return JSONResponse({
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": len(system + user) // 4, "completion_tokens": len(text) // 4},
        })

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(make_app(), host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8799)
