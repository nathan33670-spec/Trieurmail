"""Connexion Microsoft 365 par « code d'appareil » (OAuth 2.0 device code flow).

L'utilisateur ouvre https://microsoft.com/devicelogin, saisit le code affiché et se
connecte comme dans Outlook (MFA compris). Aucun mot de passe ne transite par
l'application ; seul un jeton de rafraîchissement est conservé localement (chmod 600).
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

import httpx

from .backend import MailError

SCOPES = "offline_access User.Read Mail.ReadWrite Mail.Send"
LOGIN = "https://login.microsoftonline.com"


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
        self._http = httpx.Client(timeout=30, transport=transport)
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

    # -- flux par code ------------------------------------------------------
    def start_device_flow(self) -> dict:
        self.error = ""
        resp = self._http.post(
            f"{LOGIN}/{self.tenant}/oauth2/v2.0/devicecode", data={"client_id": self.client_id, "scope": SCOPES}
        )
        data = resp.json()
        if resp.status_code >= 400:
            raise MailError(data.get("error_description", resp.text)[:400])
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
        resp = self._http.post(f"{LOGIN}/{self.tenant}/oauth2/v2.0/token", data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": self.client_id,
            "device_code": flow["device_code"],
        })
        data = resp.json()
        if resp.status_code == 200:
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
            resp = self._http.post(f"{LOGIN}/{self.tenant}/oauth2/v2.0/token", data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": self._token["refresh_token"],
                "scope": SCOPES,
            })
            data = resp.json()
            if resp.status_code != 200:
                if data.get("error") == "invalid_grant":
                    self._token = {}
                    self._save()
                raise MailError(f"Session Microsoft expirée, reconnectez-vous. ({_explain(data)})")
            self._store(data)
            return self._token["access_token"]


def _explain(data: dict) -> str:
    desc = data.get("error_description", "") or data.get("error", "erreur inconnue")
    code = desc.split(":")[0]
    hints = {
        "AADSTS65001": "Votre organisation exige l'approbation d'un administrateur pour cette application.",
        "AADSTS90094": "Votre organisation exige l'approbation d'un administrateur pour cette application.",
        "AADSTS53003": "Accès bloqué par une stratégie d'accès conditionnel de votre organisation.",
        "AADSTS700016": "Identifiant d'application (client ID) inconnu dans votre organisation.",
        "AADSTS50020": "Ce compte n'appartient pas à l'organisation indiquée (champ « tenant »).",
    }
    hint = hints.get(code)
    return f"{hint} ({code})" if hint else desc.splitlines()[0][:300]
