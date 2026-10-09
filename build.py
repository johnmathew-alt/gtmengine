#!/usr/bin/env python3
"""
TC Knowledge Engine — Build Script
Reads template.html + data.json → produces index.html

Usage:
    python3 build.py                        # reads data.json, writes index.html
    python3 build.py --data path/to/data.json --out index.html
"""
import json, sys, os, html as html_mod, argparse
from datetime import datetime, date


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def esc(text):
    """HTML-escape text."""
    return html_mod.escape(str(text))


def relevance_dots(n, total=5):
    """Render relevance dot HTML (n filled out of total)."""
    filled = '<span class="relevance-dot filled"></span>'
    empty = '<span class="relevance-dot"></span>'
    return '<span class="relevance">' + filled * n + empty * (total - n) + "</span>"


def render_stat_cards(stats):
    """Render the 4 stat cards for the Overview tab."""
    parts = []
    for s in stats:
        val = esc(s["value"])
        label = esc(s["label"])
        id_attr = f' id="{esc(s["id"])}"' if s.get("id") else ""
        parts.append(
            f'  <div class="stat-card"><div class="stat-num"{id_attr}>{val}</div>'
            f'<div class="stat-label">{label}</div></div>'
        )
    return "\n".join(parts)


def render_sentiment_bars(sentiments):
    """Render clickable sentiment bars for Overview tab."""
    parts = []
    for s in sentiments:
        label = esc(s["label"])
        pos = s["positive"]
        neu = s["neutral"]
        neg = s["negative"]
        detail = esc(s["detail"])
        parts.append(
            f'  <div class="sentiment-item" onclick="toggleSentiment(this)">\n'
            f'    <div class="sentiment-header">\n'
            f'      <span class="sentiment-label">{label}</span>\n'
            f'      <div class="sentiment-track">\n'
            f'        <div class="sentiment-pos" style="width:{pos}%">{pos}%</div>\n'
            f'        <div class="sentiment-neu" style="width:{neu}%">{neu}%</div>\n'
            f'        <div class="sentiment-neg" style="width:{neg}%">{neg}%</div>\n'
            f'      </div>\n'
            f'    </div>\n'
            f'    <div class="sentiment-detail">{detail}</div>\n'
            f'  </div>'
        )
    return "\n".join(parts)


def signal_class(signal_level):
    """Return CSS class for signal level."""
    level = signal_level.lower()
    if level == "high":
        return "signal-high"
    elif level == "medium":
        return "signal-medium"
    else:
        return "signal-watch"


def render_card(card):
    """Render a generic card (used in top signals, outbound, inbound, etc.)."""
    title = esc(card["title"])
    meta_parts = []
    if card.get("date"):
        meta_parts.append(f'<span>{esc(card["date"])}</span>')
    if card.get("meta_tags"):
        for m in card["meta_tags"]:
            meta_parts.append(f"<span>&middot;</span>")
            meta_parts.append(f'<span>{esc(m)}</span>')
    if card.get("signal"):
        cls = signal_class(card["signal"])
        label = card.get("signal_label", f'Signal: {card["signal"].upper()}')
        meta_parts.append(f"<span>&middot;</span>")
        meta_parts.append(f'<span class="{cls}">{esc(label)}</span>')
    if card.get("source_url"):
        domain = card.get("source_domain", card["source_url"].split("//")[-1].split("/")[0])
        meta_parts.append(f"<span>&middot;</span>")
        meta_parts.append(
            f'<a class="source-link" href="{esc(card["source_url"])}" target="_blank">{esc(domain)}</a>'
        )
    meta_html = "\n      ".join(meta_parts)
    body = card["body"]  # body may contain HTML (e.g. <strong> tags)
    footer_parts = []
    for tag in card.get("tags", []):
        tag_text = esc(tag["text"])
        tag_cls = tag.get("class", "tag-lime")
        footer_parts.append(f'<span class="tag {tag_cls}">{tag_text}</span>')
    if card.get("relevance"):
        footer_parts.append(relevance_dots(card["relevance"]))
    if card.get("source_url") and card.get("show_source_in_footer"):
        domain = card.get("source_domain", card["source_url"].split("//")[-1].split("/")[0])
        footer_parts.append(
            f'<a class="source-link" href="{esc(card["source_url"])}" target="_blank" style="margin-left:auto;">{esc(domain)}</a>'
        )
    footer_html = "".join(footer_parts)

    # Optional data attributes (for funding/events filters)
    attrs = ""
    if card.get("data_fgeo"):
        attrs += f' data-fgeo="{esc(card["data_fgeo"])}"'
    if card.get("data_fstage"):
        attrs += f' data-fstage="{esc(card["data_fstage"])}"'

    # Optional extra class
    extra_cls = f' {card["extra_class"]}' if card.get("extra_class") else ""

    return (
        f'    <div class="card{extra_cls}"{attrs}>\n'
        f'      <div class="card-title">{title}</div>\n'
        f'      <div class="card-meta">\n        {meta_html}\n      </div>\n'
        f'      <div class="card-body">{body}</div>\n'
        f'      <div class="card-footer">{footer_html}</div>\n'
        f'    </div>'
    )


def render_card_grid(cards):
    """Render a card-grid div with multiple cards."""
    return "\n".join(render_card(c) for c in cards)


def render_section(section):
    """Render a section with title and card grid."""
    title = esc(section["title"])
    cards_html = render_card_grid(section["cards"])
    return (
        f'<div class="section">\n'
        f'  <div class="section-title">{title}</div>\n'
        f'  <div class="card-grid">\n{cards_html}\n  </div>\n'
        f'</div>'
    )


def render_sections(sections):
    """Render multiple sections."""
    return "\n\n".join(render_section(s) for s in sections)


def render_table(table):
    """Render a tc-table from structured data."""
    headers = table["headers"]
    rows = table["rows"]

    thead = "<tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr>"
    tbody_rows = []
    for row in rows:
        cells = []
        for cell in row:
            cells.append(f"<td>{cell}</td>")  # cell may contain HTML (tags, spans)
        tbody_rows.append("<tr>" + "".join(cells) + "</tr>")
    tbody = "\n      ".join(tbody_rows)

    return (
        f'  <table class="tc-table">\n'
        f"    <thead>{thead}</thead>\n"
        f"    <tbody>\n      {tbody}\n    </tbody>\n"
        f"  </table>"
    )


def render_inbound(inbound):
    """Render the Inbound tab content."""
    parts = []
    for section in inbound.get("sections", []):
        parts.append(render_section(section))

    if inbound.get("seo_table"):
        seo = inbound["seo_table"]
        table_html = render_table(seo)
        parts.append(
            f'<div class="section">\n'
            f'  <div class="section-title">{esc(seo.get("title", "SEO / Keyword Signals"))}</div>\n'
            f'{table_html}\n'
            f'</div>'
        )
    return "\n\n".join(parts)


def render_pr(pr):
    """Render the P&R tab content."""
    parts = []

    if pr.get("dpdp_tracker"):
        tracker = pr["dpdp_tracker"]
        table_html = render_table(tracker)
        parts.append(
            f'<div class="section">\n'
            f'  <div class="section-title">{esc(tracker.get("title", "DPDP Act Tracker"))}</div>\n'
            f'{table_html}\n'
            f'</div>'
        )

    for section in pr.get("sections", []):
        parts.append(render_section(section))

    return "\n\n".join(parts)


def render_events(events):
    """Render event items with checkboxes."""
    parts = []
    for ev in events:
        eid = esc(ev["id"])
        etype = esc(ev["type"])
        ecity = esc(ev["city"])
        name = esc(ev["name"])
        meta_line = ev["meta"]  # may contain HTML entities / links
        desc = ev.get("description", "")
        tag_text = esc(ev.get("tag_text", ev["type"].capitalize()))
        tag_cls = ev.get("tag_class", "tag-lime")
        rel_label = esc(ev.get("relevance_label", "ECP Relevance:"))
        rel_n = ev.get("relevance", 3)

        parts.append(
            f'  <div class="event-item" data-etype="{etype}" data-ecity="{ecity}" data-eid="{eid}">\n'
            f'    <input type="checkbox" class="event-check" data-key="{eid}">\n'
            f'    <div class="event-info">\n'
            f'      <div class="event-name">{name}</div>\n'
            f'      <div class="event-meta">{meta_line}</div>\n'
            f'      <div class="event-meta">{desc}</div>\n'
            f'      <div class="card-footer" style="margin-top:6px;"><span class="tag {tag_cls}">{tag_text}</span>'
            f'<span>{rel_label}</span>{relevance_dots(rel_n)}</div>\n'
            f'    </div>\n'
            f'  </div>'
        )
    return "\n\n".join(parts)


def render_funding_cards(cards):
    """Render funding cards (with data attributes for filters)."""
    return render_card_grid(cards)


def render_ma_cards(cards):
    """Render M&A cards (amber border)."""
    for c in cards:
        c.setdefault("extra_class", "card-amber")
    return render_card_grid(cards)


def build(data, template_html):
    """Replace all placeholders in template with rendered content."""
    d = data

    replacements = {
        "{{DATE_DISPLAY}}": d["date_display"],
        "{{DATE_ISO}}": d["date_iso"],
        "{{STAT_CARDS}}": render_stat_cards(d["stats"]),
        "{{DPDP_BANNER_TEXT}}": d["dpdp_banner_text"],
        "{{SENTIMENT_BARS}}": render_sentiment_bars(d["sentiments"]),
        "{{TOP_SIGNALS}}": render_card_grid(d["top_signals"]),
        "{{OUTBOUND_CONTENT}}": render_sections(d["outbound"]),
        "{{INBOUND_CONTENT}}": render_inbound(d["inbound"]),
        "{{PR_CONTENT}}": render_pr(d["pr"]),
        "{{PARTNERSHIPS_CONTENT}}": render_sections(d["partnerships"]),
        "{{EVENTS_LIST}}": render_events(d["events"]),
        "{{FUNDING_CARDS}}": render_funding_cards(d["funding_cards"]),
        "{{MA_CARDS}}": render_ma_cards(d["ma_cards"]),
        "{{FUNDING_SUMMARY}}": d["funding_summary"],
    }

    output = template_html
    for placeholder, rendered in replacements.items():
        output = output.replace(placeholder, rendered)

    return output


def main():
    parser = argparse.ArgumentParser(description="Build TC Knowledge Engine dashboard")
    parser.add_argument("--data", default="data.json", help="Path to data JSON file")
    parser.add_argument("--template", default="template.html", help="Path to template HTML file")
    parser.add_argument("--out", default="index.html", help="Output HTML file")
    args = parser.parse_args()

    # Resolve paths relative to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = args.data if os.path.isabs(args.data) else os.path.join(script_dir, args.data)
    tmpl_path = args.template if os.path.isabs(args.template) else os.path.join(script_dir, args.template)
    out_path = args.out if os.path.isabs(args.out) else os.path.join(script_dir, args.out)

    data = json.loads(load(data_path))
    template = load(tmpl_path)
    result = build(data, template)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"✓ Built {out_path} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
