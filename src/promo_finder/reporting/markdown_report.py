"""Human-readable Markdown report (architecture §12.4).

Reads ``promos.json`` and writes ``report.md`` with a run summary, ranked
table, per-promo cards, and a known-limitations section.
"""

from __future__ import annotations

import json
from pathlib import Path


def _format_ts(seconds: float) -> str:
    total = max(0.0, round(seconds, 2))
    minutes = int(total // 60)
    secs = total % 60
    return f"{minutes:02d}:{secs:05.2f}"


def write_report(promos_path: str | Path, output_dir: str | Path) -> Path:
    """Generate ``report.md`` from ``promos.json`` and return its path."""
    promos_path = Path(promos_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(promos_path.read_text(encoding="utf-8"))
    run = data.get("run", {})
    promos = data.get("promos", [])

    lines: list[str] = []
    lines.append("# Promo Finder — Ranked Recommendations")
    lines.append("")
    lines.append("## Run summary")
    lines.append(f"- Mode: {run.get('llm', {}).get('mode', 'unknown')}")
    lines.append(f"- Provider: {run.get('llm', {}).get('provider', 'unknown')}")
    lines.append(f"- Eval model: {run.get('llm', {}).get('eval_model', 'unknown')}")
    lines.append(f"- Total promos: {len(promos)}")
    tiers = {}
    for p in promos:
        tiers[p.get("tier", "?")] = tiers.get(p.get("tier", "?"), 0) + 1
    lines.append(f"- Tiers: " + ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())))
    lines.append("")

    lines.append("## Ranked table")
    lines.append("")
    lines.append("| Rank | ID | Episode(s) | Segments | Duration | Score | Tier | Flags |")
    lines.append("|------|----|------------|----------|----------|-------|------|-------|")
    for p in promos:
        segs = "; ".join(
            f"{_format_ts(s['start_s'])}–{_format_ts(s['end_s'])}"
            for s in p.get("segments", [])
        )
        flags = ", ".join(p.get("flags", [])) or "—"
        lines.append(
            f"| {p.get('rank')} | {p.get('promo_id')} | "
            f"{','.join(str(e) for e in p.get('episodes', []))} | "
            f"{segs} | {p.get('total_duration_s'):.1f}s | "
            f"{p.get('score'):.1f} | {p.get('tier')} | {flags} |"
        )
    lines.append("")

    lines.append("## Per-promo cards")
    lines.append("")
    for p in promos:
        lines.append(f"### Rank {p.get('rank')} — {p.get('promo_id')} (tier {p.get('tier')}, score {p.get('score'):.1f})")
        lines.append(f"- Episodes: {', '.join(str(e) for e in p.get('episodes', []))}")
        lines.append(f"- Total duration: {p.get('total_duration_s'):.1f}s")
        lines.append(f"- Why it works: {p.get('why_it_works', '')}")
        hook = p.get("hook", {})
        cliff = p.get("cliffhanger", {})
        lines.append(f"- Hook ({hook.get('seconds_from_start', 0)}s in): “{hook.get('quote','')}” — {hook.get('description','')}")
        lines.append(f"- Cliffhanger: “{cliff.get('quote','')}” — {cliff.get('description','')}")
        if p.get("weaknesses"):
            lines.append(f"- Weaknesses: {'; '.join(p['weaknesses'])}")
        if p.get("flags"):
            lines.append(f"- Flags: {', '.join(p['flags'])}")
        lines.append("")

    lines.append("## Known limitations & where this tool picks badly")
    lines.append("")
    lines.append("- **Heuristic-only mode:** no LLM evaluation was used, so hook and "
                 "cliffhanger quality are rule-based estimates, not story judgements.")
    lines.append("- **Text-only input:** the tool sees screenplay text and timestamps, "
                 "not video, so purely visual hooks or cliffhangers may be under-scored.")
    lines.append("- **Speaker aliases:** the same character may appear under different "
                 "labels (e.g. MATRIARCH vs NOBLE MATRIARCH); descriptions may treat them as distinct.")
    lines.append("- **Resolved endings:** an episode ending is treated as a soft cliffhanger "
                 "prior, so a resolved finale may be over-scored (cf. architecture O12).")
    lines.append("- **No diversity pass:** several top promos may come from the same scene "
                 "or confrontation (MVP has overlap-dedupe but no cross-arc diversity).")
    lines.append("- **Untuned weights:** scoring weights are starting values, not fitted to "
                 "editor feedback (assumption A8).")
    lines.append("")

    report_path = output_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
