"""Connexion Microsoft 365 par « code d'appareil » (OAuth 2.0 device code flow).

L'utilisateur ouvre https://microsoft.com/devicelogin, saisit le code affiché et se
connecte comme dans Outlook (MFA compris). Aucun mot de passe ne transite par
l'application ; seul un jeton de rafraîchissement est conservé localement (chmod 600).
"""
from __future__ import annotations

import base64
import json
import os
import re
import ssl
import threading
import time
from pathlib import Path
from typing import Optional

import httpx

from .backend import MailError

SCOPES = "offline_access User.Read Mail.ReadWrite Mail.Send"
LOGIN = "https://login.microsoftonline.com"
GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
TENANT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*$")


def normalize_tenant(value: str) -> str:
    """Accepte « organizations », un domaine, un GUID, une adresse email ou une URL
    login.microsoftonline.com et renvoie la forme attendue par Microsoft."""
    t = (value or "").strip()
    if not t:
        return "organizations"
    t = re.sub(r"^https?://[^/]+/", "", t).split("/")[0]  # URL collée depuis le portail
    if "@" in t:  # adresse email saisie à la place du domaine
        t = t.rsplit("@", 1)[1]
    if not TENANT.match(t):
        raise ValueError(
            f"Organisation (tenant) invalide : « {value} ». Saisissez « organizations », « common », "
            "le domaine de l'entreprise (ex. entreprise.fr) ou l'ID d'annuaire (GUID)."
        )
    return t


def validate_client_id(value: str) -> str:
    v = (value or "").strip()
    if not GUID.match(v):
        raise ValueError(
            f"ID d'application (client ID) invalide : « {value} ». Il doit avoir la forme "
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (« ID d'application (client) » dans Microsoft Entra)."
        )
    return v


def _ssl_context():
    """Utilise le magasin de certificats du système si « truststore » est installé
    (indispensable derrière un proxy d'entreprise qui inspecte le HTTPS)."""
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:
        return True


def _network_error(exc: Exception) -> MailError:
    text = str(exc) or type(exc).__name__
    if "CERTIFICATE_VERIFY_FAILED" in text or isinstance(exc, ssl.SSLError):
        hint = ("certificat HTTPS refusé — un proxy ou antivirus d'entreprise inspecte probablement le trafic. "
                "Installez « truststore » (pip install truststore) pour utiliser les certificats du système, "
                "ou définissez SSL_CERT_FILE vers le certificat de votre entreprise")
    elif isinstance(exc, httpx.TimeoutException):
        hint = "délai dépassé"
    else:
        hint = "serveur injoignable (connexion Internet, proxy ou pare-feu ?)"
    return MailError(f"Impossible de joindre login.microsoftonline.com : {hint}. Détail : {type(exc).__name__}: {text[:300]}")


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


class GraphAuth:
    def __init__(self, client_id: str, tenant: str, token_path: Path,
                 transport: Optional[httpx.BaseTransport] = None):
        self.client_id = client_id
        self.tenant = tenant or "organizations"
        self.token_path = token_path
        self._http = httpx.Client(timeout=30, transport=transport, verify=_ssl_context())
        self._lock = threading.Lock()
        self._token: dict = self._load()
        self.flow: Optional[dict] = None  # flux de connexion en cours
        self.error = ""

    # -- stockage -----------------------------------------------------------
    def _load(self) -> dict:
        try:
            data = json.loads(self.token_path.read_text("utf-8"))
            if data.get("client_id") == self.client_id and data.get("tenant") == self.tenant:
                return data
        except (OSError, ValueError):
            pass
        return {}

    def _save(self) -> None:
        self._token.update(client_id=self.client_id, tenant=self.tenant)
        tmp = self.token_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._token), "utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.token_path)

    def _store(self, data: dict) -> None:
        claims = _claims(data.get("id_token", ""))
        self._token = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token") or self._token.get("refresh_token", ""),
            "expires_at": time.time() + int(data.get("expires_in", 3600)) - 120,
            "account": claims.get("preferred_username") or claims.get("email") or self._token.get("account", ""),
            "name": claims.get("name") or self._token.get("name", ""),
        }
        self._save()

    # -- état ---------------------------------------------------------------
    @property
    def connected(self) -> bool:
        return bool(self._token.get("refresh_token"))

    @property
    def account(self) -> str:
        return self._token.get("account", "")

    @property
    def display_name(self) -> str:
        return self._token.get("name", "")

    def status(self) -> dict:
        flow = self.flow if self.flow and self.flow["expires_at"] > time.time() else None
        return {
            "connected": self.connected,
            "account": self.account,
            "name": self.display_name,
            "pending": bool(flow),
            "user_code": flow["user_code"] if flow else "",
            "verification_uri": flow["verification_uri"] if flow else "",
            "error": self.error,
        }

    def logout(self) -> None:
        self._token = {}
        self.flow = None
        try:
            self.token_path.unlink()
        except OSError:
            pass

    # -- HTTP -----------------------------------------------------------------
    def _post(self, endpoint: str, data: dict) -> tuple[int, dict]:
        """POST vers le serveur d'authentification ; toute erreur devient un MailError explicite."""
        try:
            resp = self._http.post(f"{LOGIN}/{self.tenant}/oauth2/v2.0/{endpoint}", data=data)
        except httpx.HTTPError as exc:
            raise _network_error(exc) from exc
        except ssl.SSLError as exc:
            raise _network_error(exc) from exc
        try:
            body = resp.json()
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", resp.text)).strip()[:200]
            body = {"error": f"http_{resp.status_code}",
                    "error_description": f"Réponse inattendue de Microsoft (HTTP {resp.status_code}) : {snippet or 'vide'}"}
        return resp.status_code, body

    # -- flux par code ------------------------------------------------------
    def start_device_flow(self) -> dict:
        self.error = ""
        status, data = self._post("devicecode", {"client_id": self.client_id, "scope": SCOPES})
        if status >= 400 or "device_code" not in data:
            self.error = _explain(data)
            raise MailError(f"Connexion Microsoft refusée : {self.error}")
        self.flow = {
            "device_code": data["device_code"],
            "user_code": data["user_code"],
            "verification_uri": data.get("verification_uri", "https://microsoft.com/devicelogin"),
            "interval": int(data.get("interval", 5)),
            "expires_at": time.time() + int(data.get("expires_in", 900)),
        }
        return self.status()

    def poll_once(self) -> str:
        """'ok', 'pending' ou 'error'."""
        flow = self.flow
        if not flow:
            return "error"
        if flow["expires_at"] < time.time():
            self.flow = None
            self.error = "Le code a expiré, recommencez."
            return "error"
        try:
            status, data = self._post("token", {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": self.client_id,
                "device_code": flow["device_code"],
            })
        except MailError as exc:  # coupure passagère : on réessaie jusqu'à expiration du code
            self.error = str(exc)
            return "pending"
        if status == 200 and "access_token" in data:
            self.error = ""
            with self._lock:
                self._store(data)
            self.flow = None
            return "ok"
        err = data.get("error", "")
        if err in ("authorization_pending", "slow_down"):
            if err == "slow_down":
                flow["interval"] += 5
            return "pending"
        self.flow = None
        self.error = _explain(data)
        return "error"

    # -- jetons -------------------------------------------------------------
    def access_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            if not self.connected:
                raise MailError("Compte Microsoft 365 non connecté (Réglages → Messagerie → Se connecter).")
            if not force_refresh and self._token.get("expires_at", 0) > time.time():
                return self._token["access_token"]
            status, data = self._post("token", {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": self._token["refresh_token"],
                "scope": SCOPES,
            })
            if status != 200 or "access_token" not in data:
                if data.get("error") == "invalid_grant":
                    self._token = {}
                    self._save()
                raise MailError(f"Session Microsoft expirée, reconnectez-vous. ({_explain(data)})")
            self._store(data)
            return self._token["access_token"]


def _explain(data: dict) -> str:
    desc = str(data.get("error_description", "") or data.get("error", "") or "erreur inconnue")
    code = desc.split(":")[0].strip()
    hints = {
        "AADSTS65001": "Votre organisation exige l'approbation d'un administrateur pour cette application.",
        "AADSTS90094": "Votre organisation exige l'approbation d'un administrateur pour cette application.",
        "AADSTS53003": "Accès bloqué par une stratégie d'accès conditionnel de votre organisation.",
        "AADSTS700016": "Identifiant d'application (client ID) inconnu dans votre organisation.",
        "AADSTS50020": "Ce compte n'appartient pas à l'organisation indiquée (champ « tenant »).",
        "AADSTS50059": "Organisation introuvable : vérifiez le champ « tenant » (domaine ou ID d'annuaire).",
        "AADSTS900023": "Organisation (tenant) invalide : saisissez un domaine, un ID d'annuaire, « organizations » ou « consumers ».",
        "AADSTS90002": "Organisation introuvable : vérifiez le champ « tenant » (domaine ou ID d'annuaire).",
        "AADSTS7000218": "L'application doit autoriser les « flux de client public » (Entra → Authentification).",
        "AADSTS70002": "L'application doit autoriser les « flux de client public » (Entra → Authentification).",
        "AADSTS50194": "Application mono-organisation : renseignez le tenant (ID d'annuaire) au lieu de « organizations ».",
        "AADSTS9002346": "Application réservée aux comptes personnels : utilisez le tenant « consumers ».",
        "AADSTS50076": "Authentification multifacteur exigée : terminez la connexion dans le navigateur.",
        "AADSTS65004": "Vous avez refusé l'autorisation demandée.",
        "AADSTS70000": "Autorisation refusée ou expirée, recommencez.",
    }
    hint = hints.get(code)
    if hint:
        return f"{hint} ({code})"
    lines = desc.splitlines()
    return (lines[0] if lines else desc)[:300]
