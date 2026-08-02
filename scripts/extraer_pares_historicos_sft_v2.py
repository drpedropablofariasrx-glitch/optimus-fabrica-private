#!/usr/bin/env python3
"""Build a conservative SFT review queue from role-less chat exports.

The extractor recognizes radiology reports by their clinical section headings,
groups adjacent rewrites of the same case and keeps every new pair unapproved.
Previously reviewed rows are copied verbatim into the merged v2 queue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = Path(r"C:\Users\pedro\Proyectos Chatgpt")
DEFAULT_ABDOMEN_SOURCE = Path(
    r"C:\Users\pedro\OneDrive\Desktop\Chat GPT\Abdomen  y pelvis\Abdomen y pelvis.txt"
)
DEFAULT_PREVIOUS_QUEUE = (
    DEFAULT_HISTORY_DIR
    / "Fabrica"
    / "FABRICA_MSK"
    / "datasets"
    / "private"
    / "optimus_sft_v0"
    / "cola_revision.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "datasets" / "private" / "optimus_sft_v1"

SOURCE_SPECS = (
    ("Abdomen y pelvis.txt", "abdomen_pelvis"),
    ("RM cervical.txt", "cervical"),
    ("Rodilla.txt", "rodilla"),
    ("Rodilla2.txt", "rodilla"),
    ("Tobillo-pie.txt", "tobillo_pie"),
    ("Torax.txt", "torax"),
    ("Caadera-pelvis.txt", "cadera_pelvis"),
    ("Codo.txt", "codo"),
    ("Columna lumbar.txt", "lumbar"),
    ("Muñeca-mano.txt", "mano_muneca"),
)


def _heading(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"^\s*(?:#{{1,6}}\s*)?\*{{0,2}}{name}\s*:?\*{{0,2}}\s*(.*)$",
        re.IGNORECASE,
    )


DATA_HEADING = _heading(r"datos\s+cl[ií]nicos")
EXPLORATION_HEADING = _heading(r"exploraci[oó]n")
FINDINGS_HEADING = _heading(r"hallazgos?")
IMPRESSION_HEADING = _heading(r"impresi[oó]n\s+diagn[oó]stica")
ALL_HEADINGS = (
    DATA_HEADING,
    EXPLORATION_HEADING,
    FINDINGS_HEADING,
    IMPRESSION_HEADING,
)
STOP_AFTER_IMPRESSION = re.compile(
    r"^\s*(?:#{1,6}\s*)?\*{0,2}(?:"
    r"interpretaci[oó]n\s+global|an[aá]lisis(?:\s+complementario|\s+de\s+calidad|\s+estructurado)?|"
    r"checklist|tags|dataset(?:[_ ]training)?[_ ]entry|oportunidades\s+de\s+mejora|"
    r"alguna\s+sugerencia|ajusta\s+el\s+informe|considera\s+esto|"
    r"mi\s+correcci[oó]n|tu\s+correcci[oó]n|---+"
    r")",
    re.IGNORECASE,
)
METADATA_MARKER = re.compile(
    r"(?i)\b(?:tags|dataset(?:[_ ]training)?[_ ]entry)\b"
)
EXPLICIT_CORRECTION = re.compile(
    r"(?i)\b(?:mi\s+correcci[oó]n|informe\s+final|ajusta\s+el\s+informe|"
    r"considera\s+esto|corrige\s+el\s+informe)\b"
)
IDENTIFIER_LINE = re.compile(
    r"(?i)\b(?:sip|nhc|n[uú]mero\s+de\s+historia|historia\s+cl[ií]nica|"
    r"nombre\s+y\s+apellidos|apellidos|hospital)\b"
)
DATE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
LONG_ID = re.compile(r"\b(?:\d[ -]?){8,14}\b")

REGION_TERMS = {
    "abdomen_pelvis": ("abdomen", "abdominopelv", "higado", "riñon", "suprarrenal"),
    "torax": ("torax", "tórax", "pulmon", "pulmón", "mediastino", "angiotc pulmon"),
    "cervical": ("cervical", "cervicalgia"),
    "lumbar": ("lumbar", "lumbalgia", "l4 l5", "l5 s1"),
    "rodilla": ("rodilla", "menisco", "patelofemoral", "cruzado"),
    "mano_muneca": ("muñeca", "muneca", "mano", "carpo", "escafoides"),
    "codo": ("codo", "epicond", "olecranon"),
    "tobillo_pie": ("tobillo", "pie", "aquiles", "fascia plantar", "metatars"),
    "cadera_pelvis": ("cadera", "coxofemoral", "glute", "pelvis"),
}


@dataclass(frozen=True)
class ReportBlock:
    source_file: str
    fallback_region: str
    start_line: int
    end_line: int
    clinical: str
    exploration: str
    findings: str
    impression: str
    report_text: str
    modality: str
    region: str


def normalized(text: str) -> str:
    value = "".join(
        char
        for char in unicodedata.normalize("NFKD", text.lower())
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def sanitize(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if IDENTIFIER_LINE.search(line):
            continue
        value = DATE.sub("[FECHA]", line)
        value = EMAIL.sub("[EMAIL]", value)
        value = LONG_ID.sub("[IDENTIFICADOR]", value)
        lines.append(value.rstrip())
    return "\n".join(lines).strip()


def _section_value(
    lines: list[str],
    heading_index: int,
    match: re.Match[str],
    end_headings: tuple[re.Pattern[str], ...],
    *,
    stop_after_impression: bool = False,
) -> str:
    values = []
    inline = match.group(1).strip(" *")
    if inline:
        values.append(inline)
    for line in lines[heading_index + 1 :]:
        if any(pattern.match(line) for pattern in end_headings):
            break
        if stop_after_impression and (
            STOP_AFTER_IMPRESSION.match(line) or METADATA_MARKER.search(line)
        ):
            break
        values.append(line.rstrip())
    return sanitize("\n".join(values)).strip()


def detect_modality(exploration: str) -> str:
    value = normalized(exploration)
    if re.search(r"\b(?:tc|tac|angiotc|tomograf)", value):
        return "TC"
    if re.search(r"\b(?:rm|resonancia)", value):
        return "RM"
    if re.search(r"\b(?:eco|ecograf)", value):
        return "ECO"
    if re.search(r"\b(?:rx|radiograf)", value):
        return "RX"
    return "OTRA"


def detect_region(exploration: str, clinical: str, findings: str, fallback: str) -> str:
    exploration_value = normalized(exploration)
    context_value = normalized(f"{clinical} {findings[:500]}")
    scores = Counter()
    for region, terms in REGION_TERMS.items():
        for term in terms:
            token = normalized(term)
            if token in exploration_value:
                scores[region] += 4
            elif token in context_value:
                scores[region] += 1
    if not scores:
        return fallback
    best_region, best_score = scores.most_common(1)[0]
    fallback_score = scores.get(fallback, 0)
    return best_region if best_score >= max(3, fallback_score + 2) else fallback


def parse_report_blocks(text: str, filename: str, fallback_region: str) -> list[ReportBlock]:
    lines = text.splitlines()
    starts = [index for index, line in enumerate(lines) if DATA_HEADING.match(line)]
    blocks = []
    for sequence, start in enumerate(starts):
        end = starts[sequence + 1] if sequence + 1 < len(starts) else len(lines)
        chunk = lines[start:end]
        exploration_index = next(
            (index for index, line in enumerate(chunk) if EXPLORATION_HEADING.match(line)), None
        )
        findings_index = next(
            (index for index, line in enumerate(chunk) if FINDINGS_HEADING.match(line)), None
        )
        impression_index = next(
            (index for index, line in enumerate(chunk) if IMPRESSION_HEADING.match(line)), None
        )
        if (
            exploration_index is None
            or findings_index is None
            or impression_index is None
            or not 0 < exploration_index < findings_index < impression_index
        ):
            continue
        clinical = _section_value(
            chunk,
            0,
            DATA_HEADING.match(chunk[0]),
            (EXPLORATION_HEADING, FINDINGS_HEADING, IMPRESSION_HEADING),
        )
        exploration = _section_value(
            chunk,
            exploration_index,
            EXPLORATION_HEADING.match(chunk[exploration_index]),
            (FINDINGS_HEADING, IMPRESSION_HEADING),
        )
        findings = _section_value(
            chunk,
            findings_index,
            FINDINGS_HEADING.match(chunk[findings_index]),
            (IMPRESSION_HEADING,),
        )
        impression = _section_value(
            chunk,
            impression_index,
            IMPRESSION_HEADING.match(chunk[impression_index]),
            ALL_HEADINGS,
            stop_after_impression=True,
        )
        if len(normalized(findings)) < 25:
            continue
        report_text = format_report(clinical, exploration, findings, impression)
        blocks.append(
            ReportBlock(
                source_file=filename,
                fallback_region=fallback_region,
                start_line=start + 1,
                end_line=end,
                clinical=clinical,
                exploration=exploration,
                findings=findings,
                impression=impression,
                report_text=report_text,
                modality=detect_modality(exploration),
                region=detect_region(exploration, clinical, findings, fallback_region),
            )
        )
    return blocks


def format_report(clinical: str, exploration: str, findings: str, impression: str) -> str:
    return sanitize(
        "\n\n".join(
            (
                f"Datos clínicos: {clinical}".rstrip(),
                f"Exploración: {exploration}".rstrip(),
                f"Hallazgos:\n{findings}".rstrip(),
                f"Impresión diagnóstica:\n{impression}".rstrip(),
            )
        )
    )


def token_similarity(left: str, right: str) -> float:
    left_tokens = set(normalized(left).split())
    right_tokens = set(normalized(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def block_similarity(left: ReportBlock, right: ReportBlock) -> tuple[float, float, float, float]:
    clinical = token_similarity(left.clinical, right.clinical)
    exploration = token_similarity(left.exploration, right.exploration)
    findings = token_similarity(left.findings, right.findings)
    total = 0.25 * clinical + 0.15 * exploration + 0.60 * findings
    return total, clinical, exploration, findings


def group_blocks(blocks: list[ReportBlock]) -> list[list[ReportBlock]]:
    groups: list[list[ReportBlock]] = []
    for block in blocks:
        if not groups:
            groups.append([block])
            continue
        previous = groups[-1][-1]
        total, clinical, exploration, findings = block_similarity(previous, block)
        close = block.start_line - previous.start_line <= 250
        same_modality = previous.modality == block.modality or "OTRA" in {
            previous.modality,
            block.modality,
        }
        sufficiently_related = total >= 0.48 and (
            clinical >= 0.45 or findings >= 0.55
        )
        if close and same_modality and sufficiently_related:
            groups[-1].append(block)
        else:
            groups.append([block])
    return groups


def _stable_id(prefix: str, *values: str) -> str:
    digest = hashlib.sha256("\n".join(normalized(value) for value in values).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:16]}"


def pair_from_group(group: list[ReportBlock], source_text: str) -> dict | None:
    if len(group) < 2:
        return None
    raw = group[0]
    final_candidates = [block for block in group[1:] if len(normalized(block.impression)) >= 8]
    if not final_candidates:
        return None
    final = final_candidates[-1]
    total, clinical, exploration, findings = block_similarity(raw, final)
    between_lines = source_text.splitlines()[raw.end_line : final.start_line - 1]
    between = "\n".join(between_lines)
    empty_initial_impression = len(normalized(raw.impression)) < 8
    explicit_correction = bool(EXPLICIT_CORRECTION.search(between))
    high_confidence = (
        empty_initial_impression
        and clinical >= 0.45
        and exploration >= 0.45
        and findings >= 0.55
        and total >= 0.52
    )
    confidence = "high_structural" if high_confidence else (
        "explicit_correction_marker" if explicit_correction else "multi_version_similarity"
    )
    approval_status = "pending" if high_confidence else "candidate"
    return {
        "review_case_id": _stable_id(
            "v2",
            raw.source_file,
            raw.report_text,
            final.report_text,
        ),
        "region": final.region,
        "modality": final.modality,
        "source": {
            "file": raw.source_file,
            "lines": [raw.start_line, final.end_line],
        },
        "candidate_type": "structural_raw_final_pair_v2",
        "raw_input": raw.report_text,
        "final_report": final.report_text,
        "approval_status": approval_status,
        "review_notes": (
            "Par estructural: dictado con impresión vacía seguido de una versión relacionada."
            if high_confidence
            else "Confirmar que ambas versiones pertenecen al mismo caso y que la última es la corrección aceptada."
        ),
        "sft_eligible": False,
        "extraction_confidence": confidence,
        "similarity": {
            "total": round(total, 3),
            "clinical": round(clinical, 3),
            "exploration": round(exploration, 3),
            "findings": round(findings, 3),
        },
    }


def episode_from_group(group: list[ReportBlock]) -> dict:
    first = group[0]
    last = group[-1]
    return {
        "episode_id": _stable_id(
            "episode",
            first.source_file,
            str(first.start_line),
            first.report_text,
            last.report_text,
        ),
        "region": last.region,
        "modality": last.modality,
        "source": {"file": first.source_file, "lines": [first.start_line, last.end_line]},
        "version_count": len(group),
        "has_pair_candidate": len(group) >= 2,
        "first_report": first.report_text,
        "last_report": last.report_text,
    }


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _near_duplicate(candidate: dict, previous_rows: list[dict]) -> bool:
    candidate_file = candidate.get("source", {}).get("file")
    for row in previous_rows:
        if row.get("source", {}).get("file") != candidate_file:
            continue
        raw_similarity = token_similarity(candidate.get("raw_input", ""), row.get("raw_input", ""))
        final_similarity = token_similarity(candidate.get("final_report", ""), row.get("final_report", ""))
        if raw_similarity >= 0.88 and final_similarity >= 0.88:
            return True
    return False


def resolve_sources(history_dir: Path, abdomen_source: Path) -> list[tuple[Path, str]]:
    resolved = []
    for filename, region in SOURCE_SPECS:
        path = abdomen_source if filename == "Abdomen y pelvis.txt" else history_dir / filename
        if path.exists():
            resolved.append((path, region))
    return resolved


def build_dataset(
    sources: list[tuple[Path, str]], previous_rows: list[dict]
) -> tuple[list[dict], list[dict], dict]:
    generated_pairs = []
    episodes = []
    source_summary = {}
    for source, fallback_region in sources:
        text = source.read_text(encoding="utf-8")
        blocks = parse_report_blocks(text, source.name, fallback_region)
        groups = group_blocks(blocks)
        pairs = [pair for group in groups if (pair := pair_from_group(group, text))]
        generated_pairs.extend(pairs)
        episodes.extend(episode_from_group(group) for group in groups)
        source_summary[source.name] = {
            "report_blocks": len(blocks),
            "episodes": len(groups),
            "pair_candidates": len(pairs),
            "high_confidence": sum(row["approval_status"] == "pending" for row in pairs),
            "needs_association_review": sum(row["approval_status"] == "candidate" for row in pairs),
        }

    unique_pairs = []
    seen_ids = {row.get("review_case_id") for row in previous_rows}
    for row in generated_pairs:
        if row["review_case_id"] in seen_ids or _near_duplicate(row, previous_rows + unique_pairs):
            continue
        seen_ids.add(row["review_case_id"])
        unique_pairs.append(row)

    merged = list(previous_rows) + unique_pairs
    summary = {
        "previous_review_rows_preserved": len(previous_rows),
        "new_pair_candidates": len(unique_pairs),
        "total_review_rows": len(merged),
        "catalogued_episodes": len(episodes),
        "status": dict(Counter(row.get("approval_status", "unknown") for row in merged)),
        "sources": source_summary,
    }
    return merged, episodes, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    parser.add_argument("--abdomen-source", type=Path, default=DEFAULT_ABDOMEN_SOURCE)
    parser.add_argument("--previous-queue", type=Path, default=DEFAULT_PREVIOUS_QUEUE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    sources = resolve_sources(args.history_dir, args.abdomen_source)
    previous_rows = read_jsonl(args.previous_queue)
    merged, episodes, summary = build_dataset(sources, previous_rows)
    write_jsonl(args.output_dir / "cola_revision_v2.jsonl", merged)
    write_jsonl(args.output_dir / "catalogo_episodios_v2.jsonl", episodes)
    (args.output_dir / "resumen_extraccion_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
