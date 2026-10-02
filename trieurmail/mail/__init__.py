from ..config import MailSettings
from .backend import MailBackend, MailError
from .models import FolderInfo, MailBody, MailHeader, split_key


def create_backend(settings: MailSettings) -> MailBackend:
    if settings.provider == "imap":
        from .imap_backend import ImapBackend

        return ImapBackend(settings.imap_host, settings.imap_port, settings.imap_ssl, settings.username, settings.password)
    from .demo_backend import DemoBackend

    return DemoBackend()


__all__ = ["MailBackend", "MailError", "FolderInfo", "MailBody", "MailHeader", "split_key", "create_backend"]
