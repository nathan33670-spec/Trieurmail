from ..config import MailSettings
from .backend import MailBackend, MailError
from .models import FolderInfo, MailBody, MailHeader, split_key


def create_backend(settings: MailSettings, graph_auth=None) -> MailBackend:
    if settings.provider == "graph":
        from .graph_backend import GraphBackend

        if graph_auth is None:
            raise MailError("Connexion Microsoft 365 non initialisée")
        return GraphBackend(graph_auth)
    if settings.provider == "outlook_mac":
        from .outlook_mac_backend import OutlookMacBackend

        return OutlookMacBackend()
    if settings.provider == "imap":
        from .imap_backend import ImapBackend

        return ImapBackend(settings.imap_host, settings.imap_port, settings.imap_ssl, settings.username, settings.password)
    from .demo_backend import DemoBackend

    return DemoBackend()


__all__ = ["MailBackend", "MailError", "FolderInfo", "MailBody", "MailHeader", "split_key", "create_backend"]
