# Trieurmail

Assistant mail **local** propulsé par l'IA de votre choix (Ollama, LM Studio, vLLM, llama.cpp, LocalAI, Jan… ou toute API compatible OpenAI).

| Fonction | Ce qu'elle fait |
|---|---|
| **Trier l'historique** | L'IA analyse vos expéditeurs et **propose une arborescence de dossiers**. Vous la modifiez puis la validez, vous ajustez le classement (glisser-déposer), et rien n'est déplacé avant votre confirmation finale. Les associations expéditeur → dossier sont ensuite mémorisées pour ranger les nouveaux emails **sans IA**. |
| **Prioritaires** | Classe les emails **non lus** par urgence (score 0-100, action attendue, échéance détectée, justification courte). |
| **Synthèse** | Résumé détaillé d'un email (points clés, actions, échéance, idées de réponse), résumés express d'une liste et synthèse globale. Chaque email s'ouvre dans un lecteur intégré (HTML isolé, images distantes bloquées par défaut). |
| **Réponses pré-écrites** | Brouillon généré en streaming selon un ton (professionnel, formel, amical, bref) et une consigne libre, modifiable, puis **enregistré dans vos Brouillons** ou envoyé (SMTP) après confirmation. |
| **Périmètre / timeline** | Un histogramme du volume d'emails : glissez dessus (ou choisissez 7 j / 30 j / 3 mois…) pour ne traiter qu'une période et que certains dossiers. Toutes les fonctions respectent ce périmètre. |

## Démarrage rapide

```bash
python -m venv .venv && source .venv/bin/activate     # Windows : .venv\Scripts\activate
pip install -e .
python -m trieurmail          # ouvre http://127.0.0.1:8765
```

Au premier lancement, l'application est en **mode démo** (boîte fictive de ~350 emails) : il suffit de configurer l'IA pour tout essayer sans toucher à votre vraie boîte.

### 1. Brancher l'IA locale (Réglages → Intelligence artificielle)

Exemple avec [Ollama](https://ollama.com) :

```bash
ollama pull qwen2.5:7b-instruct      # modèle principal
ollama pull llama3.2:3b              # modèle rapide (facultatif)
```

- **URL de base** : `http://localhost:11434/v1` (préréglages fournis pour LM Studio, vLLM, llama.cpp, Jan, LocalAI)
- **Clé API** : facultative en local
- **Modèle principal** : synthèses, brouillons, conception de l'arborescence
- **Modèle rapide** (facultatif) : tâches de masse (priorisation, classement, résumés express)
- Bouton **Tester & lister les modèles** : interroge `/v1/models` et fait un appel de test.

Tous les paramètres sont réglables : température, tokens max, délai, requêtes parallèles, taille des lots, caractères max par email, mode JSON, nombre max de non lus envoyés à l'IA.

### 2. Brancher la boîte mail (Réglages → Messagerie)

Choisissez « Compte IMAP » et un fournisseur (Gmail, Outlook, Yahoo, iCloud, Orange, Free, OVH, Infomaniak) pour pré-remplir les serveurs, ou saisissez-les.

> Gmail, Yahoo et iCloud exigent un **mot de passe d'application**. Certains comptes Microsoft n'acceptent plus que OAuth, non géré pour l'instant.

## Optimisations

L'application est conçue pour qu'un modèle local, même modeste, reste utilisable sur une grosse boîte.

**Côté messagerie**
- Synchronisation **incrémentale** : seuls les en-têtes des messages inconnus sont téléchargés (lots de 200), avec un extrait de 3 Ko. Pour les messages déjà connus, seuls les drapeaux (lu, suivi) sont rafraîchis.
- `BODY.PEEK` partout : lire ou analyser ne marque jamais un email comme lu par erreur.
- Corps complets téléchargés **à la demande** puis gardés en cache. Gestion de `UIDVALIDITY` et des noms de dossiers UTF-7.
- Timeline construite à partir des seules dates de réception, avec un index incrémental.
- `MOVE` natif si disponible, déplacements groupés par plages d'UID (`1:50,72,90:120`).

**Côté IA**
- **Tri par expéditeur, pas par email** : 10 000 emails venant de 400 expéditeurs donnent 1 appel pour l'arborescence et une dizaine pour le classement (40 expéditeurs par appel, réponses sous forme d'index numériques très courtes).
- **Pré-filtrage local gratuit** : les newsletters et notifications (`List-Unsubscribe`, `Precedence: bulk`, `noreply@`…) ne sont pas envoyées à l'IA pour la priorisation. Un pré-score heuristique (destinataire direct, contact habituel, mots d'urgence, question, importance…) ne retient que les N meilleurs candidats.
- **Lots** : plusieurs emails par appel pour la priorisation et les résumés express. Les lots s'exécutent en parallèle, dans la limite réglée.
- **Double cache** : les résultats sont mis en cache par `Message-ID` (un email n'est jamais réévalué, même après déplacement) et chaque réponse brute du LLM est mise en cache par empreinte du prompt.
- **Nettoyage du texte** avant envoi : suppression des citations, signatures, HTML et longues URL, puis troncature.
- Prompts compacts, `response_format: json_object` (désactivé automatiquement si le serveur ne le gère pas), extraction JSON tolérante et une seule relance en cas de JSON invalide.
- Blocs `<think>` des modèles de raisonnement (Qwen3, DeepSeek-R1) retirés, y compris en streaming.
- Connexion HTTP keep-alive, nouvelles tentatives avec backoff sur 429/5xx, compteur de consommation visible dans la barre latérale.

## Confidentialité

- Tout tourne sur votre machine, et le serveur n'écoute que sur `127.0.0.1` par défaut.
- Vos emails ne partent que vers le serveur d'IA que vous configurez.
- Réglages et cache se trouvent dans `~/.trieurmail` (modifiable avec `TRIEURMAIL_HOME`). Le fichier de configuration est en `chmod 600` et les secrets ne sont jamais renvoyés à l'interface.
- Les emails HTML s'affichent dans une iframe sandbox, sans scripts. Une CSP bloque les images distantes (pixels de suivi) tant que vous ne cliquez pas sur « Afficher ».

## Raccourcis (boîte mail)

`j` / `k` : email suivant / précédent · `s` : résumer · `r` : répondre avec l'IA · `u` : lu / non lu · `/` : rechercher

## Architecture

```
trieurmail/
├── __main__.py            lancement (uvicorn + ouverture du navigateur)
├── config.py              réglages persistés (JSON)
├── db.py                  cache SQLite : en-têtes, corps, résultats IA, plans de tri, règles
├── mail/
│   ├── imap_backend.py    IMAP générique (lots, PEEK, MOVE, UTF-7, reconnexion)
│   ├── demo_backend.py    boîte fictive en mémoire
│   ├── parsing.py         décodage MIME, extraits, nettoyage pour le LLM
│   └── compose.py         construction des réponses, envoi SMTP
├── llm/
│   ├── client.py          client OpenAI-compatible (cache, sémaphore, retries, streaming)
│   └── prompts.py
├── services/
│   ├── sync.py            synchronisation incrémentale + timeline
│   ├── heuristics.py      pré-score local
│   ├── priority.py        feature 2
│   ├── summarizer.py      feature 3
│   ├── drafter.py         feature 4
│   ├── sorter.py          feature 1
│   └── jobs.py            tâches de fond avec progression
└── web/
    ├── app.py             API FastAPI
    └── static/            interface (HTML/CSS/JS sans build)
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Les tests utilisent la boîte démo et un faux serveur compatible OpenAI (`tests/fake_llm.py`), qu'on peut aussi lancer à la main (`python tests/fake_llm.py 8799`) pour explorer l'interface sans modèle.
