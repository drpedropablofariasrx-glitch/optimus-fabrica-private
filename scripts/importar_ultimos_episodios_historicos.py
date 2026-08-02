#!/usr/bin/env python3
"""Import recent complete report episodes from historical sources.

The import is deliberately conservative: it creates regular OPTIMUS cases for
review, never Gold/SFT examples.  Sources without complete context, mixed
anatomic regions, or a region not enabled in OPTIMUS are reported and skipped.
Run without ``--apply`` to inspect the proposed import first.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = Path(r"C:\Users\pedro\Proyectos Chatgpt")
EXTRACTOR_PATH = ROOT / "scripts" / "extraer_pares_historicos_sft_v2.py"
APP_PATH = ROOT / "00_APP" / "optimus_app.py"

# ``abdomen_pelvis`` is the name used by the historical extractor, while the
# factory's enabled region is simply ``abdomen``.
FACTORY_REGION = {"abdomen_pelvis": "abdomen"}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def raw_input(block) -> str:
    return "\n\n".join(
        part
        for part in (
            f"Datos clínicos:\n{block.clinical.strip()}" if block.clinical.strip() else "",
            f"Exploración:\n{block.exploration.strip()}" if block.exploration.strip() else "",
        )
        if part
    )


def source_marker(source: Path, first_line: int, last_line: int) -> str:
    return f"{source.name}:{first_line}-{last_line}"


def existing_source_markers(app) -> set[str]:
    markers = set()
    for region in app.list_regions():
        if not region.get("enabled"):
            continue
        config = app.get_region_config(region["region_id"])
        for case_file in config.CASES_DIR.glob("caso_*.json"):
            try:
                record = json.loads(case_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if record.get("origen") != "historial_chatgpt":
                continue
            marker = str(record.get("source_marker", ""))
            if marker:
                markers.add(marker)
    return markers


def build_candidates(extractor, app, existing_markers: set[str], per_source: int):
    enabled = {item["region_id"] for item in app.list_regions() if item.get("enabled")}
    proposed, skipped = [], []
    for source, fallback_region in extractor.resolve_sources(
        HISTORY_DIR, extractor.DEFAULT_ABDOMEN_SOURCE
    ):
        blocks = extractor.parse_report_blocks(
            source.read_text(encoding="utf-8"), source.name, fallback_region
        )
        groups = extractor.group_blocks(blocks)
        if not groups:
            skipped.append((source.name, "sin episodios estructurados"))
            continue
        region = FACTORY_REGION.get(fallback_region, fallback_region)
        if region not in enabled:
            skipped.append((source.name, f"región no habilitada: {region}"))
            continue
        selected = 0
        # These text exports do not retain a reliable global timestamp at the
        # end. Their source order is therefore used, newest complete episode first.
        for group in reversed(groups):
            first, last = group[0], group[-1]
            marker = source_marker(source, first.start_line, last.end_line)
            if marker in existing_markers:
                continue
            if not last.clinical.strip() or not last.exploration.strip() or not last.impression.strip():
                continue
            # Never promote an assistant's training metadata or internal
            # analysis into a clinical factory record.
            if app._tiene_metainfo_visible(last.report_text):
                continue
            exploration = extractor.normalized(last.exploration)
            if region == "lumbar" and "rodilla" in exploration:
                continue
            proposed.append(
                {
                    "source": source,
                    "marker": marker,
                    "region": region,
                    "modality": last.modality,
                    "raw_input": raw_input(last),
                    "report": last.report_text.strip(),
                    "versions": len(group),
                }
            )
            selected += 1
            if selected >= per_source:
                break
        if not selected:
            skipped.append((source.name, "sin episodios nuevos completos importables"))
    return proposed, skipped


def import_candidates(app, candidates, existing_markers):
    imported, skipped = [], []
    original_region = app.current_region
    try:
        for item in candidates:
            if item["marker"] in existing_markers:
                skipped.append((item["source"].name, "ya importado", item["marker"]))
                continue
            app.activar_region(item["region"])
            explanation = (
                "Importado del historial de conversación para revisión humana. "
                "No es Gold Standard ni ejemplo SFT hasta validación explícita. "
                f"Fuente: {item['marker']}."
            )
            case_id, _ = app._persistir_caso(
                item["raw_input"],
                item["report"],
                item["report"],
                region=item["region"],
                origen="historial_chatgpt",
                modalidad=item["modality"],
                explicacion=explanation,
                case_status="imported_pending",
            )
            config = app.get_region_config(item["region"])
            case_path = config.CASES_DIR / f"caso_{case_id}.json"
            record = json.loads(case_path.read_text(encoding="utf-8"))
            record["source_marker"] = item["marker"]
            record["source"] = {
                "file": item["source"].name,
                "lines": item["marker"].split(":", 1)[1],
                "kind": "historical_conversation_episode",
            }
            case_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            # Mirror the source metadata in the regional dataset row as well.
            rows = [
                json.loads(line)
                for line in config.DATASET_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            for row in reversed(rows):
                if row.get("case_id") == case_id:
                    row["source_marker"] = record["source_marker"]
                    row["source"] = record["source"]
                    break
            config.DATASET_PATH.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            imported.append((item["source"].name, item["region"], case_id, item["marker"]))
    finally:
        app.activar_region(original_region)
    return imported, skipped


def build_incomplete_knee_drafts(extractor, app, existing_markers: set[str]):
    """Return historical knee episodes with clinical context but no final impression."""
    drafts = []
    enabled = {item["region_id"] for item in app.list_regions() if item.get("enabled")}
    if "rodilla" not in enabled:
        return drafts
    for source, fallback_region in extractor.resolve_sources(
        HISTORY_DIR, extractor.DEFAULT_ABDOMEN_SOURCE
    ):
        if fallback_region != "rodilla":
            continue
        blocks = extractor.parse_report_blocks(
            source.read_text(encoding="utf-8"), source.name, fallback_region
        )
        for group in extractor.group_blocks(blocks):
            first, last = group[0], group[-1]
            marker = source_marker(source, first.start_line, last.end_line)
            if marker in existing_markers:
                continue
            if not last.clinical.strip() or not last.exploration.strip() or last.impression.strip():
                continue
            if app._tiene_metainfo_visible(last.report_text):
                continue
            drafts.append(
                {
                    "source": source,
                    "marker": marker,
                    "region": "rodilla",
                    "modality": last.modality,
                    "raw_input": raw_input(last),
                    "partial_report": last.report_text.strip(),
                    "versions": len(group),
                }
            )
    return drafts


def import_incomplete_drafts(app, drafts, existing_markers):
    imported, skipped = [], []
    original_region = app.current_region
    try:
        for item in drafts:
            if item["marker"] in existing_markers:
                skipped.append((item["source"].name, "ya importado", item["marker"]))
                continue
            app.activar_region(item["region"])
            explanation = (
                "Borrador importado del historial: hay datos clínicos y exploración, "
                "pero falta la impresión diagnóstica final. No es Gold Standard ni SFT. "
                f"Fuente: {item['marker']}."
            )
            case_id, _ = app._persistir_caso(
                item["raw_input"],
                item["partial_report"],
                "",
                region=item["region"],
                origen="historial_chatgpt",
                modalidad=item["modality"],
                explicacion=explanation,
                case_status="imported_incomplete",
            )
            config = app.get_region_config(item["region"])
            case_path = config.CASES_DIR / f"caso_{case_id}.json"
            record = json.loads(case_path.read_text(encoding="utf-8"))
            record["source_marker"] = item["marker"]
            record["source"] = {
                "file": item["source"].name,
                "lines": item["marker"].split(":", 1)[1],
                "kind": "historical_conversation_incomplete_draft",
            }
            case_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            rows = [
                json.loads(line)
                for line in config.DATASET_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            for row in reversed(rows):
                if row.get("case_id") == case_id:
                    row["source_marker"] = record["source_marker"]
                    row["source"] = record["source"]
                    break
            config.DATASET_PATH.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            imported.append((item["source"].name, item["region"], case_id, item["marker"]))
    finally:
        app.activar_region(original_region)
    return imported, skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Escribe los casos en la fábrica.")
    parser.add_argument(
        "--per-source",
        type=int,
        default=1,
        help="Número de episodios completos más recientes por fuente (por defecto: 1).",
    )
    parser.add_argument(
        "--include-incomplete-knee-drafts",
        action="store_true",
        help="Incluye los episodios de rodilla sin impresión final como borradores separados.",
    )
    parser.add_argument(
        "--only-incomplete-knee-drafts",
        action="store_true",
        help="No importa informes completos; procesa únicamente los borradores incompletos de rodilla.",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "00_APP"))
    extractor = load_module("historical_extractor", EXTRACTOR_PATH)
    app = load_module("optimus_historical_import", APP_PATH)
    existing = existing_source_markers(app)
    if args.per_source < 1:
        parser.error("--per-source debe ser al menos 1")
    if args.only_incomplete_knee_drafts and not args.include_incomplete_knee_drafts:
        parser.error("--only-incomplete-knee-drafts requiere --include-incomplete-knee-drafts")
    candidates, skipped = (
        ([], [])
        if args.only_incomplete_knee_drafts
        else build_candidates(extractor, app, existing, args.per_source)
    )
    incomplete_drafts = (
        build_incomplete_knee_drafts(extractor, app, existing)
        if args.include_incomplete_knee_drafts
        else []
    )

    summary = {
        "mode": "apply" if args.apply else "dry_run",
        "proposed": [
            {
                "file": item["source"].name,
                "region": item["region"],
                "modality": item["modality"],
                "versions": item["versions"],
                "source_marker": item["marker"],
            }
            for item in candidates
        ],
        "skipped": [{"file": file, "reason": reason} for file, reason in skipped],
        "incomplete_knee_drafts": [
            {"file": item["source"].name, "source_marker": item["marker"], "versions": item["versions"]}
            for item in incomplete_drafts
        ],
    }
    if args.apply:
        imported, duplicate_skips = import_candidates(app, candidates, existing)
        summary["imported"] = [
            {"file": file, "region": region, "case_id": case_id, "source_marker": marker}
            for file, region, case_id, marker in imported
        ]
        summary["duplicate_skips"] = [
            {"file": file, "reason": reason, "source_marker": marker}
            for file, reason, marker in duplicate_skips
        ]
        if args.include_incomplete_knee_drafts:
            draft_imported, draft_duplicate_skips = import_incomplete_drafts(app, incomplete_drafts, existing)
            summary["incomplete_knee_drafts_imported"] = [
                {"file": file, "region": region, "case_id": case_id, "source_marker": marker}
                for file, region, case_id, marker in draft_imported
            ]
            summary["incomplete_knee_draft_duplicate_skips"] = [
                {"file": file, "reason": reason, "source_marker": marker}
                for file, reason, marker in draft_duplicate_skips
            ]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
