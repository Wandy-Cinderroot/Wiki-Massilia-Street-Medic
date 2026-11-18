#!/usr/bin/env python3
"""Génère des pages index.md à partir de données exportées de Baserow
et d'un gabarit Jinja2.

Principe : tout est validé AVANT d'écrire quoi que ce soit. Au moindre
problème, le script s'arrête avec le code 1 et la liste des erreurs.

Usage :
    python3 generate.py
    python3 generate.py --pages data/pages_bad.json     (test de rejet)
    python3 generate.py --check-only
"""
import argparse
import json
import posixpath
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined

GENERATED_COMMENT = "<!-- Généré depuis Baserow : ne pas modifier à la main -->"
STATUTS = {"a-valider": "À valider", "valide": "Validé"}

SEGMENT = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# HTML, syntaxe de gabarit (Jinja / Macros), liens Markdown dans le texte libre
FORBIDDEN = re.compile(r"[<>]|\{\{|\{%|\{#|\]\(")
# Après rendu : plus aucun chevron ni syntaxe de gabarit ne doit subsister
FORBIDDEN_OUTPUT = re.compile(r"[<>]|\{\{|\{%|\{#")


# ---------------------------------------------------------------- lecture

def load_rows(path):
    """Accepte la réponse de l'API Baserow ({"results": [...]}) ou une liste."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["results"] if isinstance(data, dict) else data


def label(value):
    """Valeur d'une liste de choix Baserow : {"id": 1, "value": "x"} -> "x"."""
    return value.get("value") if isinstance(value, dict) else value


# ------------------------------------------------------------- validation

def check_text(errors, ctx, field, value, max_len, required=True, multiline=False):
    if value is None or value == "":
        if required:
            errors.append(f"{ctx}: {field} est vide")
        return
    if not isinstance(value, str):
        errors.append(f"{ctx}: {field} doit être du texte")
        return
    if len(value) > max_len:
        errors.append(f"{ctx}: {field} dépasse {max_len} caractères")
    if not multiline:
        if "\n" in value or "\r" in value:
            errors.append(f"{ctx}: {field} contient un retour à la ligne")
        if "|" in value:
            errors.append(f"{ctx}: {field} contient le caractère |")
    if FORBIDDEN.search(value) or CONTROL.search(value):
        errors.append(
            f"{ctx}: {field} contient du HTML, un lien Markdown, une syntaxe "
            "de gabarit ou un caractère de contrôle"
        )


def check_url(errors, ctx, field, value):
    u = urlparse(value) if isinstance(value, str) else None
    if (
        u is None
        or u.scheme not in ("http", "https")
        or not u.netloc
        or re.search(r"[\s<>\"'`\\]", value)
    ):
        errors.append(f"{ctx}: {field} n'est pas une URL http(s) valide")


def check_chemin(errors, ctx, chemin):
    if not isinstance(chemin, str) or not chemin:
        errors.append(f"{ctx}: chemin vide")
        return
    segments = chemin.split("/")
    if len(segments) > 3:
        errors.append(f"{ctx}: chemin trop profond (3 niveaux maximum)")
    for seg in segments:
        if not SEGMENT.match(seg):
            errors.append(
                f"{ctx}: chemin invalide '{chemin}' "
                "(minuscules, chiffres et tirets, segments séparés par /)"
            )
            return


def check_page(errors, ctx, p):
    check_text(errors, ctx, "titre", p.get("titre"), 80)
    check_text(errors, ctx, "resume", p.get("resume"), 200)
    check_text(errors, ctx, "description", p.get("description"), 3000,
               required=False, multiline=True)
    check_chemin(errors, ctx, p.get("chemin"))
    date = p.get("date_verif")
    if not isinstance(date, str) or not DATE.match(date):
        errors.append(f"{ctx}: date_verif doit être au format AAAA-MM-JJ")


def check_source(errors, ctx, s):
    check_text(errors, ctx, "nom", s.get("nom"), 120)
    check_url(errors, ctx, "lien", s.get("lien"))
    check_text(errors, ctx, "description", s.get("description"), 150, required=False)


# ------------------------------------------------------------ construction

def rel_link(target_chemin, from_chemin):
    return posixpath.relpath(target_chemin, from_chemin) + "/index.md"


def build_items(pages, sources_by_id, errors, warnings):
    by_id = {}
    for p in pages:
        if p.get("id") in by_id:
            errors.append(f"id de page en double : {p.get('id')}")
        by_id[p.get("id")] = p

    publishable, skipped = [], []
    for p in pages:
        ctx = f"page {p.get('id', '?')}"
        statut = label(p.get("statut"))
        if statut not in STATUTS:
            errors.append(f"{ctx}: statut inconnu ({statut!r})")
        elif statut == "a-valider":
            skipped.append(p)
        else:
            publishable.append(p)

    seen = {}
    for p in publishable:
        ctx = f"page {p.get('id', '?')}"
        check_page(errors, ctx, p)
        chemin = p.get("chemin")
        if chemin in seen:
            errors.append(f"{ctx}: chemin déjà utilisé par la page {seen[chemin]}")
        seen[chemin] = p.get("id")

    published = {p["id"]: p for p in publishable if p.get("id") is not None}
    items = []
    for p in publishable:
        ctx = f"page {p.get('id', '?')}"
        chemin = p.get("chemin")
        if not isinstance(chemin, str):
            continue

        contenu = [
            {
                "titre": c["titre"],
                "resume": c["resume"],
                "lien": posixpath.relpath(c["chemin"], chemin) + "/index.md",
            }
            for c in sorted(publishable, key=lambda x: str(x.get("chemin")))
            if isinstance(c.get("chemin"), str)
            and posixpath.dirname(c["chemin"]) == chemin
        ]

        sources = []
        for ref in p.get("sources") or []:
            s = sources_by_id.get(ref.get("id"))
            if s is None:
                errors.append(f"{ctx}: source introuvable (id {ref.get('id')})")
                continue
            check_source(errors, f"{ctx} source {s.get('id')}", s)
            sources.append({
                "nom": s.get("nom"),
                "lien": s.get("lien"),
                "description": s.get("description") or "",
                "contestee": bool(s.get("contestee")),
            })

        voir_aussi = []
        for ref in p.get("voir_aussi") or []:
            target = by_id.get(ref.get("id"))
            if target is None:
                errors.append(f"{ctx}: page liée introuvable (id {ref.get('id')})")
            elif target.get("id") not in published:
                warnings.append(
                    f"{ctx}: lien « voir aussi » vers la page non publiée "
                    f"{target.get('id')} ({target.get('titre')}), ignoré"
                )
            else:
                voir_aussi.append({
                    "titre": target["titre"],
                    "lien": rel_link(target["chemin"], chemin),
                })

        contributeurs = []
        for c in p.get("contributeurs") or []:
            name = label(c)
            check_text(errors, f"{ctx} contribution", "nom", name, 40)
            contributeurs.append(name)

        statut = label(p.get("statut"))
        items.append({
            "titre": p.get("titre"),
            "resume": p.get("resume"),
            "description": p.get("description") or "",
            "statut": statut,
            "statut_label": STATUTS[statut],
            "date_verif": p.get("date_verif"),
            "chemin": chemin,
            "contenu": contenu,
            "sources": sources,
            "voir_aussi": voir_aussi,
            "contributeurs": contributeurs,
        })
    return items, skipped


# ----------------------------------------------------------------- rendu

def make_env(templates_dir):
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        undefined=StrictUndefined,   # champ manquant dans le gabarit = erreur
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        autoescape=False,            # l'échappement HTML ne convient pas au Markdown
    )
    env.filters["yaml_str"] = lambda v: json.dumps(v, ensure_ascii=False)
    env.filters["md_url"] = lambda v: str(v).replace("(", "%28").replace(")", "%29")
    return env


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", default="data/pages.json")
    ap.add_argument("--sources", default="data/sources.json")
    ap.add_argument("--templates", default="templates")
    ap.add_argument("--template", default="index.md.j2")
    ap.add_argument("--out", default="out/docs")
    ap.add_argument("--check-only", action="store_true",
                    help="valide et rend en mémoire, n'écrit rien")
    args = ap.parse_args()

    pages = load_rows(args.pages)
    sources_by_id = {s["id"]: s for s in load_rows(args.sources)}

    errors, warnings = [], []
    items, skipped = build_items(pages, sources_by_id, errors, warnings)

    rendered = {}
    if not errors:
        template = make_env(args.templates).get_template(args.template)
        out_root = Path(args.out).resolve()
        for item in items:
            text = template.render(item=item)
            body = text.replace(GENERATED_COMMENT, "")
            if FORBIDDEN_OUTPUT.search(body):
                errors.append(f"{item['chemin']}: la page générée contient "
                              "du HTML ou une syntaxe de gabarit")
                continue
            target = (out_root / item["chemin"] / "index.md").resolve()
            if out_root not in target.parents:
                errors.append(f"{item['chemin']}: écriture hors du dossier de sortie")
                continue
            rendered[target] = text

    for w in warnings:
        print(f"AVERTISSEMENT {w}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} erreur(s), rien n'a été écrit :", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    if args.check_only:
        print(f"OK : {len(rendered)} page(s) valides, {len(skipped)} ignorée(s) (à valider).")
        return

    for target, text in sorted(rendered.items()):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"écrit  {target.relative_to(Path.cwd()) if Path.cwd() in target.parents else target}")
    for p in skipped:
        print(f"ignoré {p.get('chemin')} (statut à valider)")
    print(f"\n{len(rendered)} page(s) générée(s), {len(skipped)} ignorée(s).")


if __name__ == "__main__":
    main()