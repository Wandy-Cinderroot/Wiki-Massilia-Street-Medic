import json
import re
import sys
from urllib.parse import urlparse

FORBIDDEN = re.compile(
    r"[<>]|\{\{|\{%|\{#|\]\(|(?i:javascript:|data:)|[\x00-\x08\x0b\x0c\x0e-\x1f]"
)
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STATUTS = {"a-valider", "valide"}


def check_text(errors, ctx, field, value, max_len, required=True, multiline=False):
    if not value:
        if required:
            errors.append(f"{ctx}: {field} est vide")
        return
    if not isinstance(value, str):
        errors.append(f"{ctx}: {field} doit être du texte")
        return
    if len(value) > max_len:
        errors.append(f"{ctx}: {field} dépasse {max_len} caractères")
    if not multiline and ("\n" in value or "\r" in value):
        errors.append(f"{ctx}: {field} contient un retour à la ligne")
    if FORBIDDEN.search(value):
        errors.append(f"{ctx}: {field} contient du HTML, un lien, de la syntaxe de gabarit ou un caractère interdit")


def check_url(errors, ctx, field, value):
    u = urlparse(value or "")
    if u.scheme not in ("http", "https") or not u.netloc or re.search(r"[\s<>\"'`]", value):
        errors.append(f"{ctx}: {field} n'est pas une URL http(s) valide")


def check_row(row):
    errors, ctx = [], f"ligne {row.get('id', '?')}"
    check_text(errors, ctx, "titre", row.get("titre"), 80)
    check_text(errors, ctx, "resume", row.get("resume"), 200)
    check_text(errors, ctx, "description", row.get("description"), 3000, required=False, multiline=True)
    if not SLUG.match(row.get("slug") or ""):
        errors.append(f"{ctx}: slug invalide")
    if row.get("statut") not in STATUTS:
        errors.append(f"{ctx}: statut inconnu")
    if row.get("date_verif") and not DATE.match(row["date_verif"]):
        errors.append(f"{ctx}: date_verif doit être AAAA-MM-JJ")
    for i, s in enumerate(row.get("sources") or [], 1):
        c = f"{ctx} source {i}"
        check_text(errors, c, "nom", s.get("nom"), 120)
        check_url(errors, c, "lien", s.get("lien"))
        check_text(errors, c, "description", s.get("description"), 150, required=False)
    return errors


def validate_all(rows):
    errors = [e for r in rows for e in check_row(r)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)