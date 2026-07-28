#!/usr/bin/env python3
import argparse
import gzip
import html
import json
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape


def load_index(path: Path) -> dict:
    if not path.is_file():
        return {"config": {}, "docs": []}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def module_for(location: str, known_modules: set[str]) -> str | None:
    top_level = location.split("/", 1)[0]
    return top_level if top_level in known_modules else None


def merge_search(project_root: Path, reset: bool, updated_modules: list[str]) -> None:
    docs_root = project_root / "docs"
    site_root = project_root / "site"
    known_modules = {
        path.name
        for path in docs_root.iterdir()
        if path.is_dir() and path.name != "assets"
    }
    target_path = site_root / "search" / "search_index.json"
    current = {"config": {}, "docs": []} if reset else load_index(target_path)
    portal = load_index(project_root / ".site-portal" / "search" / "search_index.json")

    merged_docs = [
        document
        for document in current.get("docs", [])
        if module_for(document.get("location", ""), known_modules)
    ]
    merged_docs.extend(portal.get("docs", []))

    for module in updated_modules:
        prefix = f"{module}/"
        merged_docs = [
            document
            for document in merged_docs
            if not document.get("location", "").startswith(prefix)
        ]
        module_index = load_index(
            project_root / ".site-modules" / module / "search" / "search_index.json"
        )
        merged_docs.extend(
            document
            for document in module_index.get("docs", [])
            if document.get("location", "").startswith(prefix)
        )

    unique_docs = {}
    for document in merged_docs:
        key = (
            document.get("location", ""),
            document.get("title", ""),
            document.get("text", ""),
        )
        unique_docs[key] = document

    result = {
        "config": portal.get("config") or current.get("config", {}),
        "docs": sorted(
            unique_docs.values(),
            key=lambda document: (
                document.get("location", ""),
                document.get("title", ""),
            ),
        ),
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, separators=(",", ":"))


def load_site_url(project_root: Path) -> str:
    config_path = project_root / "mkdocs.yml"
    with config_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("site_url:"):
                site_url = line.split(":", 1)[1].strip().strip("'\"")
                if site_url:
                    return site_url.rstrip("/") + "/"
    raise RuntimeError("mkdocs.yml 中缺少 site_url")


def rebuild_sitemap(project_root: Path) -> None:
    site_root = project_root / "site"
    base_url = load_site_url(project_root)
    urls = []

    for html_file in sorted(site_root.rglob("*.html")):
        relative = html_file.relative_to(site_root).as_posix()
        if relative == "404.html":
            continue
        if relative == "index.html":
            relative = ""
        elif relative.endswith("/index.html"):
            relative = relative[: -len("index.html")]
        urls.append(base_url + quote(relative, safe="/"))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    lines.extend(f"  <url><loc>{escape(url)}</loc></url>" for url in urls)
    lines.append("</urlset>")
    sitemap = "\n".join(lines) + "\n"

    sitemap_path = site_root / "sitemap.xml"
    sitemap_path.write_text(sitemap, encoding="utf-8")
    with gzip.open(site_root / "sitemap.xml.gz", "wb") as handle:
        handle.write(sitemap.encode("utf-8"))


def ensure_module_indexes(project_root: Path) -> None:
    docs_root = project_root / "docs"
    site_root = project_root / "site"

    for docs_module in sorted(docs_root.iterdir()):
        if not docs_module.is_dir() or docs_module.name == "assets":
            continue
        module_root = site_root / docs_module.name
        module_index = module_root / "index.html"
        if (docs_module / "index.md").is_file() or not module_root.is_dir():
            continue

        candidates = sorted(
            path
            for path in module_root.rglob("index.html")
            if path != module_index
        )
        if not candidates:
            continue

        destination = candidates[0].relative_to(module_root).as_posix()
        if destination.endswith("/index.html"):
            destination = destination[: -len("index.html")]
        destination_html = html.escape(destination, quote=True)
        destination_json = json.dumps(destination, ensure_ascii=False)
        module_index.write_text(
            "\n".join(
                [
                    "<!doctype html>",
                    '<html lang="zh">',
                    "<head>",
                    '  <meta charset="utf-8">',
                    f'  <meta http-equiv="refresh" content="0; url={destination_html}">',
                    f"  <script>location.replace({destination_json});</script>",
                    f"  <title>{html.escape(docs_module.name)}</title>",
                    "</head>",
                    "<body>",
                    f'  <a href="{destination_html}">进入 {html.escape(docs_module.name)}</a>',
                    "</body>",
                    "</html>",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("modules", nargs="*")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    merge_search(project_root, args.reset, args.modules)
    ensure_module_indexes(project_root)
    rebuild_sitemap(project_root)


if __name__ == "__main__":
    main()
