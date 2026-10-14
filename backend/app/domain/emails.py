"""Нормалізація та валідація email для списків виборців."""
import re
from typing import Iterable, Optional

MAX_EMAIL_LENGTH = 255

_EMAIL_RE = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$"
)


def normalize_email(raw: str) -> str:
    """Email у списках виборців завжди зберігається в нижньому регістрі."""
    return raw.strip().lower()


def check_email(raw: object, allowed_domain: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Повертає (нормалізований_email, None) або (None, причина_відхилення)."""
    if not isinstance(raw, str) or not raw.strip():
        return None, "порожнє значення"
    email = normalize_email(raw)
    if len(email) > MAX_EMAIL_LENGTH:
        return None, "задовга адреса"
    if not _EMAIL_RE.match(email) or ".." in email:
        return None, "некоректний формат"
    if allowed_domain:
        domain = allowed_domain.lower().lstrip("@")
        if not email.endswith("@" + domain):
            return None, f"дозволено лише адреси @{domain}"
    return email, None


def parse_email_batch(
    raws: Iterable[object], allowed_domain: Optional[str]
) -> tuple[list[str], int, list[tuple[str, str]]]:
    """Розбирає пакет адрес.

    Повертає (унікальні_валідні, кількість_дублікатів_у_запиті, [(значення, причина)]).
    Некоректні значення не зупиняють обробку решти (корисно для CSV).
    """
    valid: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    invalid: list[tuple[str, str]] = []
    for raw in raws:
        email, error = check_email(raw, allowed_domain)
        if error is not None or email is None:
            shown = str(raw)[:100]
            invalid.append((shown, error or "некоректне значення"))
            continue
        if email in seen:
            duplicates += 1
            continue
        seen.add(email)
        valid.append(email)
    return valid, duplicates, invalid