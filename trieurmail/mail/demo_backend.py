"""Boîte mail fictive en mémoire pour découvrir l'application sans compte réel."""
from __future__ import annotations

import random
import threading
import time
from datetime import date, datetime, timedelta, timezone
from email import message_from_bytes
from typing import Optional

from .backend import MailBackend, MailError
from .models import FolderInfo, MailBody, MailHeader
from .parsing import BULK_SENDER_RE, decode_mime, make_snippet, parse_from

ME = "camille.martin@exemple.fr"

# (nom, adresse, bulk, [(sujet, corps)])
SENDERS = [
    ("Sophie Bernard", "sophie.bernard@acme-corp.fr", False, [
        ("Validation du budget T{q} — réponse attendue avant vendredi",
         "Bonjour Camille,\n\nPeux-tu valider le budget du trimestre avant vendredi ? Le comité de direction se réunit lundi et j'ai besoin de ton accord sur les lignes marketing (42 k€) et recrutement.\n\nMerci d'avance,\nSophie"),
        ("Point d'équipe déplacé à jeudi 14h",
         "Salut,\n\nLe point d'équipe hebdo est déplacé à jeudi 14h, salle Everest. Pense à apporter les chiffres du dernier sprint.\n\nSophie"),
        ("Revue annuelle : peux-tu remplir ton auto-évaluation ?",
         "Bonjour Camille,\n\nLa campagne de revues annuelles démarre. Merci de remplir ton auto-évaluation dans l'outil RH d'ici le 15. On planifiera ensuite un entretien d'une heure.\n\nBien à toi,\nSophie"),
    ]),
    ("Thomas Leroy", "thomas.leroy@acme-corp.fr", False, [
        ("URGENT : incident en production sur l'API de paiement",
         "Camille,\n\nL'API de paiement renvoie des erreurs 502 depuis 10h12. Environ 8 % des transactions échouent. J'ai ouvert l'incident INC-4471. Peux-tu rejoindre le canal #incident dès que possible ? On a besoin de ton feu vert pour faire un rollback.\n\nThomas"),
        ("Revue de code : refonte du module de facturation",
         "Hello,\n\nLa PR #812 (refonte facturation) est prête pour relecture. Les tests passent. J'aurais besoin de ta review d'ici mercredi si possible.\n\nThomas"),
        ("Question rapide sur l'architecture",
         "Salut Camille,\n\nOn part sur Postgres ou on garde Mongo pour le nouveau service de notifications ? J'ai besoin de trancher pour avancer.\n\nThomas"),
    ]),
    ("Maître Dubois", "cabinet@dubois-avocats.fr", False, [
        ("Signature du bail commercial — documents à retourner",
         "Madame Martin,\n\nVeuillez trouver ci-joint le bail commercial définitif. Merci de nous retourner les trois exemplaires paraphés et signés avant le 30 du mois, faute de quoi la date de prise d'effet devra être reportée.\n\nBien cordialement,\nMe Dubois"),
    ]),
    ("Maman", "francoise.martin@orange.fr", False, [
        ("Dimanche midi ?",
         "Coucou ma chérie,\n\nTu viens déjeuner dimanche ? Ton frère sera là avec les enfants. Dis-moi vite pour que je prévoie le gigot !\n\nBisous, Maman"),
        ("Photos des vacances",
         "Voici enfin les photos de la Bretagne ! Il y en a de très jolies de toi sur la plage de Trégastel.\n\nGros bisous"),
    ]),
    ("Julien Petit", "julien.petit@gmail.com", False, [
        ("Week-end escalade à Fontainebleau ?",
         "Yo Camille !\n\nOn se fait Font' le week-end du 12 ? On serait 5, je peux prendre la voiture. Tu me dis si t'es chaud.\n\nJu"),
    ]),
    ("Agence Immobilière du Centre", "location@immo-centre.fr", False, [
        ("Régularisation des charges 2025",
         "Madame,\n\nSuite à la régularisation annuelle, vous êtes redevable de 186,40 € au titre des charges 2025. Le montant sera prélevé le 5 du mois prochain sauf contestation de votre part sous 15 jours.\n\nCordialement,\nLe service gestion"),
    ]),
    ("EDF", "noreply@edf.fr", True, [
        ("Votre facture d'électricité est disponible",
         "Bonjour,\n\nVotre facture de {month} d'un montant de {amount} € est disponible dans votre espace client. Elle sera prélevée le 12.\n\nEDF"),
    ]),
    ("Free", "facturation@free-mobile.fr", True, [
        ("Votre facture Free Mobile",
         "Bonjour,\n\nVotre facture mensuelle de {amount} € est disponible dans votre espace abonné.\n\nL'équipe Free"),
    ]),
    ("BNP Paribas", "ne-pas-repondre@bnpparibas.fr", True, [
        ("Votre relevé de compte est disponible",
         "Madame,\n\nVotre relevé de compte du mois de {month} est disponible dans votre espace client.\n\nBNP Paribas"),
        ("Alerte : opération importante sur votre compte",
         "Madame,\n\nUne opération de {amount} € a été effectuée sur votre compte. Si vous n'êtes pas à l'origine de cette opération, contactez immédiatement votre conseiller.\n\nBNP Paribas"),
    ]),
    ("Impots.gouv", "ne-pas-repondre@dgfip.finances.gouv.fr", True, [
        ("Votre avis d'impôt est disponible",
         "Madame,\n\nVotre avis d'impôt sur les revenus est disponible dans votre espace particulier. Date limite de paiement : 15 septembre.\n\nLa DGFiP"),
    ]),
    ("Amazon.fr", "confirmation-commande@amazon.fr", True, [
        ("Votre commande n°{order} a été expédiée",
         "Bonjour Camille,\n\nVotre commande ({item}) a été expédiée et sera livrée demain.\n\nAmazon.fr"),
        ("Confirmation de commande n°{order}",
         "Merci pour votre commande : {item}. Total : {amount} €.\n\nAmazon.fr"),
    ]),
    ("SNCF Connect", "noreply@sncf-connect.com", True, [
        ("Votre e-billet Paris → Lyon",
         "Bonjour,\n\nVoici votre e-billet pour le trajet Paris Gare de Lyon → Lyon Part-Dieu, départ 07h56, voiture 14 place 82.\n\nBon voyage !"),
    ]),
    ("Airbnb", "automated@airbnb.com", True, [
        ("Réservation confirmée à Lisbonne",
         "Votre réservation à Lisbonne (3 nuits) est confirmée. Arrivée à partir de 15h.\n\nAirbnb"),
    ]),
    ("GitHub", "notifications@github.com", True, [
        ("[acme/billing] PR #{order}: fix rounding in invoices",
         "@thomas-leroy requested your review on this pull request.\n\nView it on GitHub."),
        ("[acme/api] Run failed: CI - main",
         "The workflow CI failed on main. 3 jobs failed.\n\nView workflow run on GitHub."),
    ]),
    ("Jira", "jira@acme-corp.atlassian.net", True, [
        ("[JIRA] PAY-{order} assigné à vous",
         "Le ticket PAY-{order} « Erreur d'arrondi sur les avoirs » vous a été assigné par Sophie Bernard."),
    ]),
    ("LinkedIn", "messages-noreply@linkedin.com", True, [
        ("Vous avez 3 nouvelles invitations",
         "Camille, des personnes souhaitent rejoindre votre réseau. Voir les invitations."),
        ("Un recruteur a consulté votre profil",
         "Votre profil a été consulté 14 fois cette semaine."),
    ]),
    ("Le Monde", "newsletter@lemonde.fr", True, [
        ("La Matinale du Monde",
         "Les informations essentielles du jour : politique, économie, international. Bonne lecture."),
    ]),
    ("Welcome to the Jungle", "newsletter@welcometothejungle.com", True, [
        ("10 offres qui pourraient vous plaire",
         "Product Manager, Lead Dev, Engineering Manager… découvrez les offres de la semaine."),
    ]),
    ("Decathlon", "news@decathlon.fr", True, [
        ("-30 % sur l'escalade ce week-end",
         "Profitez de -30 % sur toute la gamme escalade jusqu'à dimanche. Offre réservée aux membres."),
    ]),
    ("Doctolib", "no-reply@doctolib.fr", True, [
        ("Rappel : rendez-vous demain avec Dr Moreau",
         "Rappel de votre rendez-vous demain à 9h30 avec le Dr Moreau, médecin généraliste. Pensez à votre carte Vitale."),
    ]),
    ("Mutuelle Santé+", "service@mutuelle-santeplus.fr", False, [
        ("Remboursement effectué",
         "Madame,\n\nUn remboursement de {amount} € a été effectué sur votre compte au titre de vos soins du {month}.\n\nVotre mutuelle"),
    ]),
]

MONTHS = "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split()
ITEMS = ["Casque Bose QC45", "Livre « Clean Architecture »", "Chaussons d'escalade", "Câble USB-C", "Cafetière italienne"]


def _generate() -> list[dict]:
    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    mails: list[dict] = []
    for name, addr, bulk, templates in SENDERS:
        count = rng.randint(12, 30) if bulk else rng.randint(2, 7)
        for n in range(count):
            subject, body = templates[0] if n == 0 else rng.choice(templates)
            age = rng.random() ** 1.6 * 540  # plus de mails récents
            if n == 0 and not bulk:
                age = rng.random() * 3  # quelques demandes récentes non lues
            dt = now - timedelta(days=age, minutes=rng.randint(0, 1440))
            fmt = dict(
                q=(dt.month - 1) // 3 + 1,
                month=MONTHS[dt.month - 1],
                amount=f"{rng.uniform(9, 320):.2f}".replace(".", ","),
                order=rng.randint(100, 9999),
                item=rng.choice(ITEMS),
            )
            mails.append(dict(
                name=name, addr=addr, bulk=bulk, subject=subject.format(**fmt), body=body.format(**fmt),
                date=int(dt.timestamp()), seen=age > 6 or (bulk and rng.random() < 0.3),
            ))
    mails.sort(key=lambda m: m["date"])
    return mails


class DemoBackend(MailBackend):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.delimiter = "/"
        self.folders: dict[str, dict] = {}
        self._next_uid: dict[str, int] = {}
        for name in ("INBOX", "Brouillons", "Envoyés", "Corbeille"):
            self._add_folder(name)
        for m in _generate():
            self._store("INBOX", m)

    def _add_folder(self, name: str) -> None:
        self.folders.setdefault(name, {})
        self._next_uid.setdefault(name, 1)

    def _store(self, folder: str, m: dict) -> int:
        uid = self._next_uid[folder]
        self._next_uid[folder] += 1
        m = dict(m)
        m.setdefault("message_id", f"<demo-{folder}-{uid}-{m['date']}@exemple.fr>")
        m.setdefault("flagged", False)
        m.setdefault("answered", False)
        self.folders[folder][uid] = m
        return uid

    def list_folders(self):
        special = {"Brouillons": "drafts", "Envoyés": "sent", "Corbeille": "trash"}
        with self._lock:
            names = sorted(self.folders, key=lambda n: (n != "INBOX", n.lower()))
            return [FolderInfo(n, "/", [], special.get(n)) for n in names]

    def _get(self, folder: str) -> dict:
        if folder not in self.folders:
            raise MailError(f"Dossier inconnu : {folder}")
        return self.folders[folder]

    def search(self, folder, since, before, unseen=False):
        with self._lock:
            out = []
            for uid, m in self._get(folder).items():
                d = datetime.fromtimestamp(m["date"], timezone.utc).date()
                if since and d < since:
                    continue
                if before and d >= before:
                    continue
                if unseen and m["seen"]:
                    continue
                out.append(uid)
            return 1, sorted(out)

    def fetch_headers(self, folder, uids):
        with self._lock:
            box = self._get(folder)
            out = []
            for uid in uids:
                m = box.get(uid)
                if not m:
                    continue
                bulk = m.get("bulk", False) or bool(BULK_SENDER_RE.search(m["addr"]))
                out.append(MailHeader(
                    folder=folder, uidvalidity=1, uid=uid, message_id=m["message_id"],
                    subject=m["subject"], from_name=m["name"], from_addr=m["addr"],
                    to_addrs=m.get("to", ME), cc_addrs="", date=m["date"], seen=m["seen"],
                    flagged=m["flagged"], answered=m["answered"], snippet=make_snippet(m["body"]),
                    size=len(m["body"]), is_bulk=bulk,
                    in_reply_to=m.get("in_reply_to", ""), references=m.get("references", ""),
                    high_importance="URGENT" in m["subject"],
                ))
            return out

    def fetch_flags(self, folder, uids):
        with self._lock:
            box = self._get(folder)
            return {u: (box[u]["seen"], box[u]["flagged"], box[u]["answered"]) for u in uids if u in box}

    def fetch_dates(self, folder, min_uid):
        with self._lock:
            return 1, [(u, m["date"]) for u, m in self._get(folder).items() if u >= min_uid]

    def fetch_body(self, folder, uid):
        with self._lock:
            m = self._get(folder).get(uid)
            if not m:
                raise MailError("Message introuvable (déplacé ou supprimé ?)")
            text = m["body"]
            html = "<div style='font-family:sans-serif'>" + "".join(
                f"<p>{line}</p>" for line in text.split("\n\n")
            ).replace("\n", "<br>") + "</div>"
            headers = {
                "From": f"{m['name']} <{m['addr']}>", "To": m.get("to", ME), "Subject": m["subject"],
                "Date": datetime.fromtimestamp(m["date"]).strftime("%a, %d %b %Y %H:%M:%S"),
                "Message-ID": m["message_id"],
            }
            return MailBody(text=text, html=html, attachments=[], headers=headers)

    def set_seen(self, folder, uids, seen):
        with self._lock:
            for u in uids:
                if u in self._get(folder):
                    self.folders[folder][u]["seen"] = seen

    def create_folder(self, name):
        with self._lock:
            parts = name.split("/")
            for i in range(1, len(parts) + 1):
                self._add_folder("/".join(parts[:i]))

    def move(self, folder, uids, dest):
        with self._lock:
            src = self._get(folder)
            self._get(dest)
            for u in uids:
                m = src.pop(u, None)
                if m:
                    self._store(dest, m)

    def append(self, folder, raw, flags=""):
        with self._lock:
            msg = message_from_bytes(raw)
            name, addr = parse_from(msg.get("From", ""))
            payload = msg.get_payload(decode=True) if not msg.is_multipart() else b""
            self._store(folder, dict(
                name=name or "Moi", addr=addr or ME, bulk=False, subject=decode_mime(msg.get("Subject")),
                body=(payload or b"").decode("utf-8", errors="replace"), date=int(time.time()),
                seen=True, to=msg.get("To", ""),
            ))
