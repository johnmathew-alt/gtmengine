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
    if card.get("data_country"):
        attrs += f' data-country="{esc(card["data_country"])}"'
    if card.get("data_threat"):
        attrs += f' data-threat="{esc(card["data_threat"])}"'
    if card.get("data_otype"):
        attrs += f' data-otype="{esc(card["data_otype"])}"'

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


def render_table(table, row_data_attr=None, row_data_col=None):
    """Render a tc-table from structured data.

    row_data_attr: if set, add this data attribute to each <tr>
    row_data_col: column index to extract the value from (parsed from signal-* class or lowercased text)
    """
    headers = table["headers"]
    rows = table["rows"]

    thead = "<tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr>"
    tbody_rows = []
    for row in rows:
        cells = []
        for cell in row:
            cells.append(f"<td>{cell}</td>")  # cell may contain HTML (tags, spans)
        tr_attrs = ""
        if row_data_attr is not None and row_data_col is not None and row_data_col < len(row):
            cell_val = row[row_data_col]
            # Extract from signal-high/medium/low class or fall back to text
            import re
            m = re.search(r'signal-(high|medium|low|watch)', cell_val)
            if m:
                level = m.group(1)
                if level == "watch":
                    level = "low"
                tr_attrs = f' data-{row_data_attr}="{level}"'
            else:
                # Strip HTML tags before using as attribute value
                clean_val = re.sub(r'<[^>]+>', '', cell_val).strip().lower()
                tr_attrs = f' data-{row_data_attr}="{esc(clean_val)}"'
        tbody_rows.append(f"<tr{tr_attrs}>" + "".join(cells) + "</tr>")
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


def render_cld(cld):
    """Render the CLD tab content (sections with country-filtered cards)."""
    parts = []
    for section in cld.get("sections", []):
        parts.append(render_section(section))
    if cld.get("table"):
        table = cld["table"]
        table_html = render_table(table)
        parts.append(
            f'<div class="section">\n'
            f'  <div class="section-title">{esc(table.get("title", "Market Statistics"))}</div>\n'
            f'{table_html}\n'
            f'</div>'
        )
    return "\n\n".join(parts)


def render_competitors(competitors):
    """Render the Competitors tab content."""
    parts = []
    if competitors.get("table"):
        table = competitors["table"]
        # Find the "Threat Level" column index for data-threat attribute
        threat_col = None
        for i, h in enumerate(table["headers"]):
            if "threat" in h.lower():
                threat_col = i
                break
        table_html = render_table(table, row_data_attr="threat", row_data_col=threat_col)
        parts.append(
            f'<div class="section">\n'
            f'  <div class="section-title">{esc(table.get("title", "Competitor Landscape"))}</div>\n'
            f'{table_html}\n'
            f'</div>'
        )
    for section in competitors.get("sections", []):
        parts.append(render_section(section))
    return "\n\n".join(parts)


def render_offerings(offerings):
    """Render the Offerings tab content."""
    parts = []
    for section in offerings.get("sections", []):
        parts.append(render_section(section))
    return "\n\n".join(parts)


def render_legaltech(legaltech):
    """Render the Legal Tech tab content."""
    parts = []
    for section in legaltech.get("sections", []):
        parts.append(render_section(section))
    return "\n\n".join(parts)


def render_scorecard(scorecard):
    """Render the executive scorecard for Overview tab."""
    if not scorecard:
        return ""
    items = scorecard.get("items", [])
    if not items:
        return ""
    parts = []
    for item in items:
        metric = esc(item["metric"])
        value = esc(item["value"])
        trend_dir = item.get("trend", "flat")  # up, down, flat
        trend_text = esc(item.get("trend_text", ""))
        status = item.get("status", "green")  # green, amber, red

        # Sparkline SVG if data points provided
        spark_html = ""
        spark_data = item.get("sparkline", [])
        if spark_data and len(spark_data) >= 2:
            max_v = max(spark_data) or 1
            min_v = min(spark_data)
            rng = max_v - min_v or 1
            w = 100
            h = 24
            pts = []
            for i, v in enumerate(spark_data):
                x = (i / (len(spark_data) - 1)) * w
                y = h - ((v - min_v) / rng) * (h - 4) - 2
                pts.append(f"{x:.1f},{y:.1f}")
            polyline = " ".join(pts)
            color = "#5f7a1f" if trend_dir == "up" else ("#b23b2a" if trend_dir == "down" else "#6b6b6b")
            spark_html = (
                f'<div class="scorecard-spark">'
                f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none">'
                f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
                f'</svg></div>'
            )

        trend_cls = trend_dir
        arrow = "▲" if trend_dir == "up" else ("▼" if trend_dir == "down" else "—")

        parts.append(
            f'<div class="scorecard-item sc-{status}">\n'
            f'  <div class="scorecard-metric">{metric}</div>\n'
            f'  <div class="scorecard-value">{value}</div>\n'
            f'  <div class="scorecard-trend {trend_cls}">{arrow} {trend_text}</div>\n'
            f'{spark_html}\n'
            f'</div>'
        )
    return f'<div class="scorecard">\n' + "\n".join(parts) + '\n</div>'


def render_actions(actions):
    """Render recommended actions bar for a tab."""
    if not actions:
        return ""
    items = actions.get("items", [])
    if not items:
        return ""
    title = esc(actions.get("title", "Recommended Actions"))
    parts = []
    for item in items:
        priority = item.get("priority", "soon")  # now, soon, plan
        text = item["text"]  # may contain HTML
        parts.append(
            f'  <div class="action-item">\n'
            f'    <span class="action-priority ap-{priority}">{priority.upper()}</span>\n'
            f'    <span class="action-text">{text}</span>\n'
            f'  </div>'
        )
    return (
        f'<div class="actions-bar">\n'
        f'  <div class="actions-bar-title">{title}</div>\n'
        + "\n".join(parts) +
        f'\n</div>'
    )


def render_battlecards(battlecards):
    """Render expandable battlecards for high-threat competitors."""
    if not battlecards:
        return ""
    parts = []
    parts.append('<div class="section">\n  <div class="section-title">Competitive Battlecards</div>')
    for bc in battlecards:
        name = esc(bc["name"])
        threat = esc(bc.get("threat", "high"))
        threat_tag = f'<span class="tag tag-red" style="font-size:11px">{threat.upper()} THREAT</span>'
        strengths = bc.get("strengths", [])
        weaknesses = bc.get("weaknesses", [])
        win_strategy = bc.get("win_strategy", "")
        s_items = "".join(f"<li>{esc(s)}</li>" for s in strengths)
        w_items = "".join(f"<li>{esc(w)}</li>" for w in weaknesses)
        win_html = ""
        if win_strategy:
            win_html = (
                f'<div class="bc-win"><h4>How TC Wins</h4>'
                f'<p>{esc(win_strategy)}</p></div>'
            )
        parts.append(
            f'  <div class="battlecard" data-threat="{threat}">\n'
            f'    <div class="battlecard-header">\n'
            f'      <div class="battlecard-name">{name} {threat_tag}</div>\n'
            f'      <span class="battlecard-toggle">▾</span>\n'
            f'    </div>\n'
            f'    <div class="battlecard-body">\n'
            f'      <div class="bc-grid">\n'
            f'        <div class="bc-col bc-strengths"><h4>Their Strengths</h4><ul>{s_items}</ul></div>\n'
            f'        <div class="bc-col bc-weaknesses"><h4>Their Weaknesses</h4><ul>{w_items}</ul></div>\n'
            f'      </div>\n'
            f'{win_html}\n'
            f'    </div>\n'
            f'  </div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


def render_win_loss(win_loss):
    """Render win/loss tracking section for Competitors tab."""
    if not win_loss:
        return ""
    parts = []
    parts.append('<div class="section">\n  <div class="section-title">Win / Loss Tracking</div>\n  <div class="winloss-grid">')

    # Overall stats card
    overall = win_loss.get("overall", {})
    if overall:
        wins = overall.get("wins", 0)
        losses = overall.get("losses", 0)
        total = wins + losses or 1
        rate = round((wins / total) * 100)
        parts.append(
            f'    <div class="winloss-card">\n'
            f'      <h4>Overall Record</h4>\n'
            f'      <div class="winloss-stat"><span class="winloss-label">Wins</span><span class="winloss-value win">{wins}</span></div>\n'
            f'      <div class="winloss-stat"><span class="winloss-label">Losses</span><span class="winloss-value loss">{losses}</span></div>\n'
            f'      <div class="winloss-stat"><span class="winloss-label">Win Rate</span><span class="winloss-value rate">{rate}%</span></div>\n'
            f'      <div class="winloss-bar-track"><div class="winloss-bar-fill fill-green" style="width:{rate}%"></div></div>\n'
            f'    </div>'
        )

    # By competitor
    by_competitor = win_loss.get("by_competitor", [])
    if by_competitor:
        rows = ""
        for c in by_competitor:
            name = esc(c["name"])
            w = c.get("wins", 0)
            l = c.get("losses", 0)
            t = w + l or 1
            r = round((w / t) * 100)
            color = "fill-green" if r >= 60 else ("fill-amber" if r >= 40 else "fill-red")
            rows += (
                f'      <div class="winloss-stat"><span class="winloss-label">{name}</span>'
                f'<span class="winloss-value">{w}W / {l}L ({r}%)</span></div>\n'
                f'      <div class="winloss-bar-track"><div class="winloss-bar-fill {color}" style="width:{r}%"></div></div>\n'
            )
        parts.append(f'    <div class="winloss-card">\n      <h4>By Competitor</h4>\n{rows}    </div>')

    # Objection themes
    objections = win_loss.get("objections", [])
    if objections:
        obj_html = ""
        for o in objections:
            theme = esc(o["theme"])
            freq = o.get("frequency", 0)
            obj_html += f'      <div class="objection-item"><span class="objection-freq">{freq}×</span>{theme}</div>\n'
        parts.append(f'    <div class="winloss-card">\n      <h4>Top Objection Themes</h4>\n{obj_html}    </div>')

    # Win rate trend
    trend = win_loss.get("trend", [])
    if trend and len(trend) >= 2:
        max_v = max(t.get("rate", 0) for t in trend) or 1
        w = 100
        h = 40
        pts = []
        for i, t in enumerate(trend):
            x = (i / (len(trend) - 1)) * w
            y = h - (t.get("rate", 0) / 100) * (h - 4) - 2
            pts.append(f"{x:.1f},{y:.1f}")
        polyline = " ".join(pts)
        labels = "".join(f'<span style="font-size:10px;color:var(--tc-muted)">{esc(t.get("period",""))}</span>' for t in trend)
        parts.append(
            f'    <div class="winloss-card">\n      <h4>Win Rate Trend</h4>\n'
            f'      <svg viewBox="0 0 {w} {h}" style="width:100%;height:40px" preserveAspectRatio="none">'
            f'<polyline points="{polyline}" fill="none" stroke="#5f7a1f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>\n'
            f'      <div style="display:flex;justify-content:space-between;margin-top:4px">{labels}</div>\n'
            f'    </div>'
        )

    parts.append('  </div>\n</div>')
    return "\n".join(parts)


def render_funding_table(funding_table):
    """Render the India funding report table."""
    if not funding_table:
        return ""
    return (
        f'<div class="section">\n'
        f'  <div class="section-title">{esc(funding_table.get("title", "India Startup Funding — Seed to Series A ($1M–$100M)"))}</div>\n'
        f'{render_table(funding_table)}\n'
        f'</div>'
    )


def build(data, template_html):
    """Replace all placeholders in template with rendered content."""
    d = data

    replacements = {
        "{{DATE_DISPLAY}}": d["date_display"],
        "{{DATE_ISO}}": d["date_iso"],
        "{{SCORECARD}}": render_scorecard(d.get("scorecard")),
        "{{STAT_CARDS}}": render_stat_cards(d["stats"]),
        "{{DPDP_BANNER_TEXT}}": d["dpdp_banner_text"],
        "{{SENTIMENT_BARS}}": render_sentiment_bars(d["sentiments"]),
        "{{TOP_SIGNALS}}": render_card_grid(d["top_signals"]),
        "{{OUTBOUND_ACTIONS}}": render_actions(d.get("outbound_actions")),
        "{{OUTBOUND_CONTENT}}": render_sections(d["outbound"]),
        "{{INBOUND_ACTIONS}}": render_actions(d.get("inbound_actions")),
        "{{INBOUND_CONTENT}}": render_inbound(d["inbound"]),
        "{{PR_ACTIONS}}": render_actions(d.get("pr_actions")),
        "{{PR_CONTENT}}": render_pr(d["pr"]),
        "{{PARTNERSHIPS_ACTIONS}}": render_actions(d.get("partnerships_actions")),
        "{{PARTNERSHIPS_CONTENT}}": render_sections(d["partnerships"]),
        "{{EVENTS_LIST}}": render_events(d["events"]),
        "{{FUNDING_CARDS}}": render_funding_cards(d["funding_cards"]),
        "{{MA_CARDS}}": render_ma_cards(d["ma_cards"]),
        "{{FUNDING_SUMMARY}}": d["funding_summary"],
        "{{CLD_CONTENT}}": render_cld(d["cld"]) if d.get("cld") else "",
        "{{CLD_SUMMARY}}": d.get("cld_summary", ""),
        "{{COMPETITORS_ACTIONS}}": render_actions(d.get("competitors_actions")),
        "{{COMPETITORS_CONTENT}}": render_competitors(d["competitors"]) if d.get("competitors") else "",
        "{{WIN_LOSS}}": render_win_loss(d.get("win_loss")),
        "{{BATTLECARDS}}": render_battlecards(d.get("battlecards")),
        "{{COMPETITORS_SUMMARY}}": d.get("competitors_summary", ""),
        "{{OFFERINGS_CONTENT}}": render_offerings(d["offerings"]) if d.get("offerings") else "",
        "{{OFFERINGS_SUMMARY}}": d.get("offerings_summary", ""),
        "{{LEGALTECH_CONTENT}}": render_legaltech(d["legaltech"]) if d.get("legaltech") else "",
        "{{LEGALTECH_SUMMARY}}": d.get("legaltech_summary", ""),
        "{{FUNDING_TABLE}}": render_funding_table(d.get("funding_table")),
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
