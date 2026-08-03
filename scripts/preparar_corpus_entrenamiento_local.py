#!/usr/bin/env python3
"""Prepara activos locales para estilo, SFT y evaluación de OPTIMUS.

El script solo lee informes ya aprobados. No cambia prompts, no llama a ningún
proveedor y no entrena un modelo. Su salida queda bajo ``datasets/private``:

* perfiles_estilo_region_modalidad.json: descripción estadística del estilo.
* sft_train.jsonl: pares dictado/informe final para un futuro fine-tuning.
* benchmark_holdout.jsonl: casos reservados para medir el modelo, nunca para
  entrenarlo.
* manifiesto_corpus.json: recuentos, origen y criterios reproducibles.

La separación train/benchmark es estable por hash y se hace por región; así un
caso nunca aparece en ambos conjuntos. Los grupos pequeños quedan completos en
entrenamiento para no vaciar regiones escasas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "datasets" / "private"
DEFAULT_OUTPUT = PRIVATE / "optimus_training_v1"
DEFAULT_STYLE_QUEUE = PRIVATE / "optimus_style_v1" / "candidatos_estilo_por_revisar.jsonl"
DEFAULT_SFT_QUEUES = (
    PRIVATE / "optimus_sft_v1" / "cola_revision_v2.jsonl",
    PRIVATE / "vuepacs_import" / "pendientes_revision.jsonl",
)
SECTION_LABELS = (
    "datos clinicos",
    "exploracion",
    "hallazgos",
    "impresion diagnostica",
)
SYSTEM_MESSAGE = (
    "Redacta el informe radiológico en español con formato de texto plano para PACS. "
    "Conserva únicamente los datos del caso aportado; no inventes hallazgos ni recomendaciones."
)
MIN_REGION_CASES_FOR_HOLDOUT = 8
HOLDOUT_RATIO = 0.15


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def normalizar(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or "")).lower()
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\W+", " ", value).strip()


def palabras(text: str) -> int:
    return len(re.findall(r"\w+", text, flags=re.UNICODE))


def tiene_posible_identificador(text: str) -> bool:
    """Cortafuegos conservador adicional antes de exportar para SFT."""
    if re.search(r"\b(?:sip|nhc|numero de historia|nombre y apellidos)\b", normalizar(text)):
        return True
    if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I):
        return True
    return bool(re.search(r"\b(?:\d[ -]?){8,14}\b", text))


def identidad_estable(*parts: str) -> str:
    payload = "\x1f".join(normalizar(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def modalidad(row: dict) -> str:
    value = str(row.get("modality") or "").strip().upper()
    return value if value and value not in {"SIN_CLASIFICAR", "OTRA"} else "DESCONOCIDA"


def perfil_de_grupo(rows: list[dict]) -> dict:
    informes = [str(row["report"]).strip() for row in rows]
    cuentas_secciones = {
        etiqueta: sum(etiqueta in normalizar(informe) for informe in informes)
        for etiqueta in SECTION_LABELS
    }
    longitudes = sorted(palabras(informe) for informe in informes)
    return {
        "report_count": len(informes),
        "average_words": round(statistics.mean(longitudes), 1),
        "median_words": statistics.median(longitudes),
        "section_coverage": {
            etiqueta: round(cuentas_secciones[etiqueta] / len(informes), 3)
            for etiqueta in SECTION_LABELS
        },
    }


def construir_perfiles(style_rows: list[dict], sft_rows: list[dict]) -> dict:
    por_region: dict[str, list[dict]] = defaultdict(list)
    por_region_modalidad: dict[tuple[str, str], list[dict]] = defaultdict(list)
    vistos = set()

    for row in style_rows + sft_rows:
        informe = str(row.get("report") or row.get("final_report") or "").strip()
        region = str(row.get("region") or "sin_clasificar")
        clave = normalizar(informe)
        if not informe or clave in vistos:
            continue
        vistos.add(clave)
        item = {"report": informe, "source": row.get("source", {})}
        por_region[region].append(item)
        if row in sft_rows:
            por_region_modalidad[(region, modalidad(row))].append(item)

    return {
        "schema_version": "optimus-style-profile-v2",
        "purpose": (
            "Perfil estadístico local de redacción. No contiene reglas clínicas "
            "nuevas ni sustituye la revisión humana."
        ),
        "style_reports_used": len(style_rows),
        "approved_sft_reports_used": len(sft_rows),
        "profiles_by_region": {
            region: perfil_de_grupo(rows)
            for region, rows in sorted(por_region.items())
        },
        "profiles_by_region_modality": {
            f"{region}|{mod}": {"region": region, "modality": mod, **perfil_de_grupo(rows)}
            for (region, mod), rows in sorted(por_region_modalidad.items())
        },
    }


def pares_aprobados(queues: Iterable[Path]) -> tuple[list[dict], Counter]:
    pairs, discarded = [], Counter()
    seen = set()
    for queue in queues:
        for row in read_jsonl(queue):
            if row.get("approval_status") != "approved" or not row.get("sft_eligible"):
                discarded["not_approved_or_ineligible"] += 1
                continue
            raw = str(row.get("raw_input") or "").strip()
            final = str(row.get("final_report") or "").strip()
            if not raw or not final:
                discarded["missing_pair_member"] += 1
                continue
            if tiene_posible_identificador(raw + "\n" + final):
                discarded["possible_identifier"] += 1
                continue
            pair_id = identidad_estable(str(row.get("review_case_id") or ""), raw, final)
            if pair_id in seen:
                discarded["duplicate"] += 1
                continue
            seen.add(pair_id)
            pairs.append(
                {
                    "training_pair_id": f"pair_{pair_id}",
                    "region": str(row.get("region") or "sin_clasificar"),
                    "modality": modalidad(row),
                    "source": row.get("source") if isinstance(row.get("source"), dict) else {},
                    "source_queue": queue.name,
                    "messages": [
                        {"role": "system", "content": SYSTEM_MESSAGE},
                        {"role": "user", "content": raw},
                        {"role": "assistant", "content": final},
                    ],
                }
            )
    return pairs, discarded


def separar_train_y_benchmark(pairs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Reserva un holdout estable por región sin dejar grupos pequeños vacíos."""
    por_region: dict[str, list[dict]] = defaultdict(list)
    for pair in pairs:
        por_region[pair["region"]].append(pair)
    train, benchmark = [], []
    for region, rows in sorted(por_region.items()):
        ordenados = sorted(rows, key=lambda row: row["training_pair_id"])
        if len(ordenados) < MIN_REGION_CASES_FOR_HOLDOUT:
            train.extend(ordenados)
            continue
        n_holdout = max(1, round(len(ordenados) * HOLDOUT_RATIO))
        benchmark.extend(ordenados[:n_holdout])
        train.extend(ordenados[n_holdout:])
    return train, benchmark


def build(style_queue: Path, sft_queues: Iterable[Path]) -> tuple[list[dict], list[dict], dict]:
    style_rows = [
        row for row in read_jsonl(style_queue)
        if row.get("approval_status") == "approved" and str(row.get("report") or "").strip()
    ]
    approved_sft, discarded = pares_aprobados(sft_queues)
    train, benchmark = separar_train_y_benchmark(approved_sft)
    sft_profile_rows = [
        {
            "region": pair["region"],
            "modality": pair["modality"],
            "final_report": pair["messages"][2]["content"],
            "source": pair["source"],
        }
        for pair in approved_sft
    ]
    manifest = {
        "schema_version": "optimus-local-training-v1",
        "status": "prepared_not_trained",
        "style_profiles": construir_perfiles(style_rows, sft_profile_rows),
        "sft": {
            "approved_pairs": len(approved_sft),
            "train_pairs": len(train),
            "benchmark_pairs": len(benchmark),
            "holdout_ratio": HOLDOUT_RATIO,
            "minimum_region_cases_for_holdout": MIN_REGION_CASES_FOR_HOLDOUT,
            "discarded": dict(discarded),
        },
        "safety": {
            "prompts_modified": False,
            "provider_calls_made": False,
            "training_performed": False,
            "train_and_benchmark_disjoint": not {
                row["training_pair_id"] for row in train
            }.intersection(row["training_pair_id"] for row in benchmark),
        },
    }
    return train, benchmark, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--style-queue", type=Path, default=DEFAULT_STYLE_QUEUE)
    parser.add_argument("--sft-queue", action="append", type=Path, default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    queues = args.sft_queue or list(DEFAULT_SFT_QUEUES)
    train, benchmark, manifest = build(args.style_queue, queues)
    if not args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(args.output_dir / "sft_train.jsonl", train)
        write_jsonl(args.output_dir / "benchmark_holdout.jsonl", benchmark)
        (args.output_dir / "perfiles_estilo_region_modalidad.json").write_text(
            json.dumps(manifest["style_profiles"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (args.output_dir / "manifiesto_corpus.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(manifest["sft"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
