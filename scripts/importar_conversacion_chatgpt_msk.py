from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUEUE = (
    PROJECT_ROOT
    / "datasets"
    / "private"
    / "optimus_sft_v1"
    / "cola_revision_v2.jsonl"
)

CORRECTION_RE = re.compile(
    r"^\s*(?:mi\s+)?(?:correcci[oó]n|versi[oó]n\s+corregida|informe\s+corregido)"
    r"(?:\s+final)?\s*[:.-]?\s*",
    re.IGNORECASE,
)
REPORT_HEADER_RE = re.compile(
    r"(?im)^[ \t]*(?:[*#]+[ \t]*)?"
    r"(datos\s+cl[ií]nicos|exploraci[oó]n|hallazgos|impresi[oó]n\s+diagn[oó]stica)"
    r"[ \t]*(?:[*]+)?[ \t]*:?"
)
REPORT_END_RE = re.compile(
    r"(?im)^[ \t]*(?:[*#]+[ \t]*)?"
    r"(?:interpretaci[oó]n\s+global|an[aá]lisis(?:\s+complementario)?|mostrar\s+m[aá]s)"
    r"\b"
)
IDENTIFIER_LINE_RE = re.compile(
    r"^\s*(?:paciente|nombre(?:\s+y\s+apellidos)?|apellidos|edad|sexo|"
    r"g[eé]nero|edad\s*,\s*g[eé]nero(?:\s+y\s+hospital)?|sip|nhc|dni|"
    r"historia\s+cl[ií]nica|n[uú]mero\s+de\s+historia|fecha\s+de\s+nacimiento|"
    r"hospital|dr\.?|dra\.?)\s*:",
    re.IGNORECASE,
)

REGION_TERMS = {
    "hombro": ("hombro", "glenohumeral", "supraespinoso", "infraespinoso"),
    "rodilla": ("rodilla", "menisco", "patelofemoral"),
    "tobillo_pie": ("tobillo", "pie", "aquiles", "talonavicular"),
    "codo": ("codo", "epicond"),
    "mano_muneca": ("muñeca", "muneca", "carpo", "metacarp"),
    "lumbar": ("lumbar", "lumbosacra"),
    "cervical": ("cervical",),
    "torax": ("tórax", "torax"),
    "abdomen_pelvis": ("abdomen", "abdominopélv", "abdominopelv"),
    "cadera_pelvis": ("cadera", "pelvis ósea", "pelvis osea"),
}


def sanitize_text(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line for line in text.splitlines() if not IDENTIFIER_LINE_RE.match(line)]
    text = "\n".join(lines)
    text = re.sub(r"\bSIP\s*[:#-]?\s*\d+\b", "[SIP]", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(?:hospital\s+la\s+fe|vithas)\b",
        "[HOSPITAL]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:hombre|mujer|var[oó]n)\s*,?\s*(?:de\s*)?\d{1,3}\s*a[nñ]os\b",
        "[DEMOGRAFIA]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        "[EMAIL]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:\+?34\s*)?(?:\d[\s.-]?){9}\b",
        "[TELEFONO]",
        text,
    )
    text = re.sub(
        r"\b\d{1,2}[/.:-]\d{1,2}[/.:-](?:\d{2}|\d{4})"
        r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\b",
        "[FECHA]",
        text,
    )
    text = re.sub(r"\b\d{7,16}\b", "[ID]", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_report(value: str, *, remove_correction_marker: bool = False) -> str:
    text = sanitize_text(value)
    if remove_correction_marker:
        text = CORRECTION_RE.sub("", text, count=1)

    first_header = REPORT_HEADER_RE.search(text)
    if not first_header:
        return ""
    text = text[first_header.start() :]

    end = REPORT_END_RE.search(text)
    if end:
        text = text[: end.start()]

    text = re.sub(r"(?im)^\s*mostrar\s+m[aá]s\s*$", "", text)
    text = text.replace("**", "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def report_headers(value: str) -> set[str]:
    return {
        plain(re.sub(r"\s+", " ", match.group(1).lower()))
        for match in REPORT_HEADER_RE.finditer(value)
    }


def is_raw_report(value: str) -> bool:
    return {
        "datos clinicos",
        "exploracion",
        "hallazgos",
    }.issubset(report_headers(value))


def is_complete_report(value: str) -> bool:
    return is_raw_report(value) and "impresion diagnostica" in report_headers(value)


def ensure_empty_impression(value: str) -> str:
    report = clean_report(value)
    if "impresion diagnostica" not in report_headers(report):
        report = report.rstrip() + "\n\nImpresión diagnóstica:\n"
    return report


def plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def impression_text(value: str) -> str:
    report = clean_report(value)
    matches = list(REPORT_HEADER_RE.finditer(report))
    for index, match in enumerate(matches):
        if plain(match.group(1).lower()) != "impresion diagnostica":
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report)
        return report[match.end() : end].strip(" \t\n:-")
    return ""


def token_similarity(left: str, right: str) -> float:
    stopwords = {
        "datos",
        "clinicos",
        "exploracion",
        "hallazgos",
        "impresion",
        "diagnostica",
        "informe",
        "correccion",
    }

    def tokens(value: str) -> set[str]:
        normalized = re.sub(r"[^a-z0-9ñ]+", " ", plain(value).casefold())
        return {
            token
            for token in normalized.split()
            if len(token) > 3 and token not in stopwords
        }

    left_tokens = tokens(left)
    right_tokens = tokens(right)
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def detect_region(*values: str) -> str:
    normalized = " ".join(values).casefold()
    scores = {
        region: sum(term.casefold() in normalized for term in terms)
        for region, terms in REGION_TERMS.items()
    }
    region, score = max(scores.items(), key=lambda item: item[1])
    return region if score else "sin_clasificar"


def detect_modality(value: str) -> str:
    normalized = value.casefold()
    if "artro-rm" in normalized or "artro rm" in normalized:
        return "ARTRO-RM"
    if re.search(r"\brm\b", normalized):
        return "RM"
    if re.search(r"\btc\b", normalized):
        return "TC"
    if "ecograf" in normalized:
        return "US"
    if re.search(r"\brx\b", normalized):
        return "RX"
    return "sin_clasificar"


def stable_id(*parts: str) -> str:
    payload = "\0".join(parts).encode("utf-8")
    return "chatgpt_" + hashlib.sha256(payload).hexdigest()[:20]


def source_metadata(
    metadata: dict[str, Any],
    source_file: str,
    turns: list[str],
) -> dict[str, Any]:
    return {
        "file": source_file,
        "platform": "chatgpt",
        "project": metadata.get("project", ""),
        "conversation_title": metadata.get("conversation_title", ""),
        "conversation_id": metadata.get("conversation_id", ""),
        "turns": turns,
    }


def extract_correction_pairs(document: dict[str, Any], source_file: str) -> list[dict]:
    metadata = document.get("source") or {}
    messages = document.get("messages") or []
    pairs: list[dict] = []

    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        user_text = sanitize_text(message.get("text", ""))
        if not CORRECTION_RE.match(user_text):
            continue

        previous = next(
            (
                candidate
                for candidate in reversed(messages[max(0, index - 6) : index])
                if candidate.get("role") == "assistant"
                and is_complete_report(clean_report(candidate.get("text", "")))
            ),
            None,
        )
        if not previous:
            continue

        raw_report = clean_report(previous.get("text", ""))
        final_report = clean_report(user_text, remove_correction_marker=True)
        if not (is_complete_report(raw_report) and is_complete_report(final_report)):
            continue

        previous_turn = str(previous.get("turn_id", ""))
        final_turn = str(message.get("turn_id", ""))
        region = detect_region(raw_report, final_report)
        pairs.append(
            {
                "review_case_id": stable_id(
                    str(metadata.get("conversation_id", "")),
                    previous_turn,
                    final_turn,
                    raw_report,
                    final_report,
                ),
                "region": region,
                "modality": detect_modality(final_report),
                "source": source_metadata(
                    metadata,
                    source_file,
                    [previous_turn, final_turn],
                ),
                "candidate_type": "chatgpt_draft_correction_pair",
                "training_task": "draft_to_corrected_report",
                "raw_input": raw_report,
                "final_report": final_report,
                "approval_status": "candidate",
                "review_notes": (
                    "Corrección explícita del radiólogo sobre un borrador del modelo. "
                    "No usar como dictado→informe; revisar para el conjunto borrador→corrección."
                ),
                "sft_eligible": False,
                "extraction_confidence": "explicit_user_correction_of_model_draft",
            }
        )
    return pairs


def _following_assistant_report(
    messages: list[dict[str, Any]],
    raw_index: int,
) -> tuple[int, dict[str, Any], str] | None:
    for index in range(raw_index + 1, min(len(messages), raw_index + 4)):
        message = messages[index]
        if message.get("role") == "user":
            return None
        if message.get("role") != "assistant":
            continue
        report = clean_report(message.get("text", ""))
        if is_complete_report(report):
            return index, message, report
    return None


def _following_correction(
    messages: list[dict[str, Any]],
    assistant_index: int,
    draft_report: str,
) -> tuple[dict[str, Any], str, str] | None:
    for message in messages[assistant_index + 1 : assistant_index + 5]:
        if message.get("role") != "user":
            continue
        text = sanitize_text(message.get("text", ""))
        report = clean_report(
            text,
            remove_correction_marker=bool(CORRECTION_RE.match(text)),
        )
        if not is_complete_report(report) or len(impression_text(report)) < 15:
            continue
        similarity = token_similarity(draft_report, report)
        if CORRECTION_RE.match(text):
            return message, report, "explicit_user_correction"
        if similarity >= 0.45:
            return message, report, "structural_user_correction"
    return None


def extract_review_pairs(
    document: dict[str, Any],
    source_file: str,
    *,
    expected_region: str | None = None,
) -> list[dict]:
    metadata = document.get("source") or {}
    messages = document.get("messages") or []
    pairs: list[dict] = []
    linked_correction_turns: set[str] = set()

    for raw_index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        raw_report = clean_report(message.get("text", ""))
        if not is_raw_report(raw_report) or len(impression_text(raw_report)) >= 15:
            continue
        raw_report = ensure_empty_impression(raw_report)

        assistant_match = _following_assistant_report(messages, raw_index)
        if not assistant_match:
            continue
        assistant_index, assistant_message, draft_report = assistant_match

        region = detect_region(raw_report, draft_report)
        if expected_region and region != expected_region:
            continue

        raw_turn = str(message.get("turn_id", ""))
        assistant_turn = str(assistant_message.get("turn_id", ""))
        final_report = draft_report
        turns = [raw_turn, assistant_turn]
        candidate_type = "chatgpt_raw_generated_pair"
        training_task = "raw_to_generated_report"
        approval_status = "candidate"
        confidence = "conversation_adjacency"
        notes = (
            "Dictado seguido de un informe generado por el modelo. "
            "Editar y aprobar manualmente antes de usar para entrenamiento."
        )

        correction = _following_correction(messages, assistant_index, draft_report)
        if correction:
            correction_message, final_report, confidence = correction
            correction_turn = str(correction_message.get("turn_id", ""))
            linked_correction_turns.add(correction_turn)
            turns.append(correction_turn)
            candidate_type = "chatgpt_raw_final_correction_candidate"
            training_task = "raw_to_corrected_report"
            approval_status = "pending"
            notes = (
                "Dictado, borrador y corrección posterior reconstruidos de la conversación. "
                "Confirmar la asociación antes de aprobar."
            )

        pairs.append(
            {
                "review_case_id": stable_id(
                    str(metadata.get("conversation_id", "")),
                    raw_turn,
                    assistant_turn,
                    turns[-1],
                    raw_report,
                    final_report,
                ),
                "region": region,
                "modality": detect_modality(final_report),
                "source": source_metadata(metadata, source_file, turns),
                "candidate_type": candidate_type,
                "training_task": training_task,
                "raw_input": raw_report,
                "final_report": final_report,
                "approval_status": approval_status,
                "review_notes": notes,
                "sft_eligible": False,
                "extraction_confidence": confidence,
            }
        )

    for correction_pair in extract_correction_pairs(document, source_file):
        final_turn = str(correction_pair.get("source", {}).get("turns", ["", ""])[-1])
        if final_turn in linked_correction_turns:
            continue
        if expected_region and correction_pair.get("region") != expected_region:
            continue
        pairs.append(correction_pair)

    return pairs


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def merge_rows(existing: Iterable[dict], candidates: Iterable[dict]) -> tuple[list[dict], int]:
    merged = list(existing)
    seen = {row.get("review_case_id") for row in merged}
    seen_conversation_turns = {
        (
            row.get("source", {}).get("conversation_id"),
            tuple(row.get("source", {}).get("turns", []))[-1],
        )
        for row in merged
        if row.get("source", {}).get("conversation_id")
        and row.get("source", {}).get("turns")
    }
    added = 0
    for candidate in candidates:
        if candidate.get("review_case_id") in seen:
            continue
        source = candidate.get("source", {})
        turns = tuple(source.get("turns", []))
        conversation_turn = (
            source.get("conversation_id"),
            turns[-1] if turns else None,
        )
        if (
            conversation_turn[0]
            and conversation_turn[1]
            and conversation_turn in seen_conversation_turns
        ):
            continue
        merged.append(candidate)
        seen.add(candidate.get("review_case_id"))
        if conversation_turn[0] and conversation_turn[1]:
            seen_conversation_turns.add(conversation_turn)
        added += 1
    return merged, added


def atomic_write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importa casos revisables de conversaciones MSK de ChatGPT."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--region")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    document = json.loads(args.input.read_text(encoding="utf-8-sig"))
    candidates = extract_review_pairs(
        document,
        args.input.name,
        expected_region=args.region,
    )
    existing = read_jsonl(args.queue)
    merged, added = merge_rows(existing, candidates)

    if not args.dry_run:
        atomic_write_jsonl(args.queue, merged)

    print(
        json.dumps(
            {
                "conversation": document.get("source", {}).get(
                    "conversation_title", ""
                ),
                "detected_pairs": len(candidates),
                "raw_generated_pairs": sum(
                    row.get("candidate_type") == "chatgpt_raw_generated_pair"
                    for row in candidates
                ),
                "raw_corrected_pairs": sum(
                    row.get("candidate_type")
                    == "chatgpt_raw_final_correction_candidate"
                    for row in candidates
                ),
                "draft_correction_pairs": sum(
                    row.get("candidate_type") == "chatgpt_draft_correction_pair"
                    for row in candidates
                ),
                "added_pairs": added,
                "queue_total": len(merged),
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
