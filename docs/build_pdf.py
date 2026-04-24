"""Render ARCHITECTURE.md to a standalone HTML file with print CSS.

Usage:
    python3 docs/build_pdf.py

Open docs/ARCHITECTURE.html in Safari / Chrome, then File → Print → Save as PDF.

Only stdlib — no pip install needed.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MD = ROOT / "ARCHITECTURE.md"
OUT = ROOT / "ARCHITECTURE.html"


CSS = """
@page { size: A4; margin: 20mm 18mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: -apple-system, "Inter", "Helvetica Neue", Arial, sans-serif;
  color: #111;
  max-width: 780px;
  margin: 2rem auto;
  line-height: 1.55;
  font-size: 11.5pt;
  padding: 0 1rem;
}
h1, h2, h3, h4 {
  color: #111;
  page-break-after: avoid;
  line-height: 1.2;
}
h1 { font-size: 26pt; border-bottom: 2px solid #ef4444; padding-bottom: 0.3rem; margin-top: 1rem; }
h2 { font-size: 18pt; margin-top: 2rem; color: #b91c1c; }
h3 { font-size: 13pt; margin-top: 1.5rem; }
hr { border: 0; border-top: 1px solid #ddd; margin: 2rem 0; }
code {
  font-family: "SF Mono", "Menlo", Consolas, monospace;
  background: #f5f5f5;
  padding: 0 0.25rem;
  border-radius: 3px;
  font-size: 0.92em;
}
pre {
  background: #0b0b0f;
  color: #e8e8ee;
  padding: 14px 16px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 9pt;
  line-height: 1.35;
  page-break-inside: avoid;
}
pre code { background: none; color: inherit; padding: 0; font-size: inherit; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 1rem 0;
  font-size: 10pt;
  page-break-inside: avoid;
}
th, td {
  border: 1px solid #ddd;
  padding: 6px 10px;
  text-align: left;
  vertical-align: top;
}
th { background: #f7f7f9; }
blockquote {
  border-left: 3px solid #ef4444;
  padding: 0.3rem 1rem;
  color: #444;
  background: #fff6f5;
  margin: 1rem 0;
}
header.cover {
  border: 1px solid #eee;
  padding: 2rem;
  border-radius: 12px;
  background: linear-gradient(180deg, #fff 0%, #fafafa 100%);
  margin-bottom: 2.5rem;
}
header.cover h1 { border: 0; margin: 0; font-size: 32pt; }
header.cover .sub { color: #666; font-size: 14pt; margin-top: 0.5rem; }
header.cover .meta { color: #888; font-size: 10pt; margin-top: 1rem; }
a { color: #b91c1c; }
ul, ol { padding-left: 1.4rem; }
li { margin: 0.2rem 0; }
.anchor { scroll-margin-top: 80px; }
"""


def md_to_html(md_text: str) -> tuple[str, dict]:
    """Tiny, purpose-built Markdown → HTML. Handles what the document uses:
    headings, paragraphs, lists, tables, code fences, horizontal rules,
    bold/italic, inline code. Not general-purpose."""
    lines = md_text.splitlines()
    out: list[str] = []
    i = 0
    meta: dict = {}

    # YAML front-matter
    if lines and lines[0].strip() == "---":
        j = 1
        while j < len(lines) and lines[j].strip() != "---":
            if ":" in lines[j]:
                k, _, v = lines[j].partition(":")
                meta[k.strip()] = v.strip().strip('"')
            j += 1
        i = j + 1

    while i < len(lines):
        line = lines[i]

        if line.strip() == "":
            out.append("")
            i += 1
            continue

        # code fence
        if line.startswith("```"):
            i += 1
            buf: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
            continue

        # horizontal rule
        if line.strip() == "---":
            out.append("<hr/>")
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # table (header row with pipes + separator row of dashes)
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", lines[i + 1]):
            out.append(_render_table(lines, i_start=i, consume=lambda new_i: None))
            # advance past the table
            while i < len(lines) and lines[i].strip().startswith("|"):
                i += 1
            continue

        # unordered list
        if re.match(r"^\s*[-*]\s+", line):
            items: list[str] = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + "</ul>")
            continue

        # ordered list
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + "</ol>")
            continue

        # paragraph — collect until blank / block-level
        buf = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not _is_block(lines[i]):
            buf.append(lines[i])
            i += 1
        out.append("<p>" + _inline(" ".join(buf)) + "</p>")

    return "\n".join(out), meta


def _inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", s)
    return s


def _is_block(line: str) -> bool:
    return (
        line.startswith("#") or line.startswith("```") or line.strip() == "---"
        or re.match(r"^\s*[-*]\s+", line) is not None
        or re.match(r"^\s*\d+\.\s+", line) is not None
        or line.strip().startswith("|")
    )


def _render_table(lines: list[str], i_start: int, consume) -> str:
    header = [c.strip() for c in lines[i_start].strip().strip("|").split("|")]
    j = i_start + 2
    rows: list[list[str]] = []
    while j < len(lines) and lines[j].strip().startswith("|"):
        rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
        j += 1
    parts = ["<table><thead><tr>"]
    for h in header:
        parts.append(f"<th>{_inline(h)}</th>")
    parts.append("</tr></thead><tbody>")
    for r in rows:
        parts.append("<tr>")
        for c in r:
            parts.append(f"<td>{_inline(c)}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def main() -> int:
    md = MD.read_text()
    body, meta = md_to_html(md)

    title = meta.get("title", "ScamLens — Architecture")
    subtitle = meta.get("subtitle", "")
    date = meta.get("date", "")
    author = meta.get("author", "")

    cover = (
        '<header class="cover">'
        f'<h1>{html.escape(title)}</h1>'
        + (f'<div class="sub">{html.escape(subtitle)}</div>' if subtitle else "")
        + f'<div class="meta">{html.escape(author)} · {html.escape(date)}</div>'
        + "</header>"
    )

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{cover}
{body}
</body>
</html>
"""
    OUT.write_text(doc)
    print(f"[scamlens] wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"Open: open {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
