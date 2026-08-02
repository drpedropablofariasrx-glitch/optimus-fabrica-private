#!/usr/bin/env python3
"""Prepara un corpus local y revisable para aprender el estilo de OPTIMUS.

No modifica prompts, reglas clínicas ni la cola SFT existente.  Los informes
históricos completos se conservan como *candidatos de estilo* hasta que el
radiólogo los apruebe expresamente.  El perfil activo se calcula únicamente
con informes ya aprobados en las colas operativas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "datasets" / "private" / "optimus_style_v1"
DEFAULT_QUEUES = (
    ROOT / "datasets" / "private" / "optimus_sft_v1" / "cola_revision_v2.jsonl",
    ROOT / "datasets" / "private" / "vuepacs_import" / "pendientes_revision.jsonl",
)

SECTION_NAMES = ("datos clinicos", "exploracion", "hallazgos", "impresion diagnostica")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).lower()
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\W+", " ", value).strip()


def report_from_current(row: dict) -> str:
    return str(row.get("final_report") or row.get("informe_final") or "").strip()


def has_complete_sections(report: str) -> bool:
    text = normalized(report)
    return all(section in text for section in SECTION_NAMES)


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"style_{digest}"


def summarize_active(approved: list[dict]) -> dict:
    by_region: dict[str, list[dict]] = defaultdict(list)
    for row in approved:
        by_region[row.get("region") or "sin_clasificar"].append(row)

    regions = {}
    for region, rows in sorted(by_region.items()):
        reports = [report_from_current(row) for row in rows]
        regions[region] = {
            "approved_reports": len(rows),
            "reports_with_complete_sections": sum(has_complete_sections(report) for report in reports),
            "average_words": round(sum(word_count(report) for report in reports) / len(reports), 1),
            "median_words": sorted(word_count(report) for report in reports)[len(reports) // 2],
        }
    return {
        "schema_version": "optimus-style-profile-v1",
        "purpose": "Estadísticas locales; no contiene instrucciones clínicas nuevas.",
        "active_source": "solo casos SFT aprobados",
        "approved_reports": len(approved),
        "regions": regions,
    }


def build(queues: list[Path], legacy_dir: Path) -> tuple[list[dict], list[dict], dict]:
    current = [row for queue in queues for row in read_jsonl(queue)]
    approved = [row for row in current if row.get("approval_status") == "approved" and report_from_current(row)]
    current_reports = {normalized(report_from_current(row)) for row in current if report_from_current(row)}

    candidates: list[dict] = []
    seen = set()
    scanned = Counter()
    complete = Counter()
    excluded_as_duplicate = Counter()
    for path in sorted(legacy_dir.glob("*_historico_dataset.jsonl")):
        for row in read_jsonl(path):
            region = row.get("region") or "sin_clasificar"
            scanned[region] += 1
            report = str(row.get("report_candidate") or "").strip()
            if not has_complete_sections(report):
                continue
            complete[region] += 1
            report_key = normalized(report)
            if not report_key or report_key in current_reports or report_key in seen:
                excluded_as_duplicate[region] += 1
                continue
            seen.add(report_key)
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            candidates.append(
                {
                    "style_candidate_id": stable_id(region, report),
                    "region": region,
                    "report": report,
                    "source": source,
                    "candidate_type": row.get("candidate_type", "historical_report"),
                    "approval_status": "candidate",
                    "style_eligible": False,
                    "review_notes": "Informe histórico completo. Revisar y aprobar antes de usarlo como ejemplo de estilo.",
                }
            )

    summary = {
        "schema_version": "optimus-style-audit-v1",
        "active_approved_reports": len(approved),
        "historical_rows_scanned": sum(scanned.values()),
        "historical_complete_reports": sum(complete.values()),
        "historical_complete_duplicates_excluded": sum(excluded_as_duplicate.values()),
        "new_style_candidates": len(candidates),
        "by_region": {
            region: {
                "historical_rows": scanned[region],
                "historical_complete": complete[region],
                "duplicates_excluded": excluded_as_duplicate[region],
                "new_candidates": complete[region] - excluded_as_duplicate[region],
            }
            for region in sorted(scanned)
        },
    }
    return approved, candidates, {"summary": summary, "profile": summarize_active(approved)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--queue", action="append", type=Path, default=[])
    args = parser.parse_args()

    queues = args.queue or list(DEFAULT_QUEUES)
    if not args.legacy_dir.exists():
        raise SystemExit(f"No existe el directorio histórico: {args.legacy_dir}")
    approved, candidates, result = build(queues, args.legacy_dir)
    if not args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(args.output_dir / "candidatos_estilo_por_revisar.jsonl", candidates)
        (args.output_dir / "perfil_estilo_activo.json").write_text(
            json.dumps(result["profile"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (args.output_dir / "resumen_auditoria_estilo.json").write_text(
            json.dumps(result["summary"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
