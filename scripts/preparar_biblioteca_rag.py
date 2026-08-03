#!/usr/bin/env python3
"""Ingesta local de bibliografia en PDF para la biblioteca RAG de OPTIMUS.

Fase 1 (extraccion y troceado): convierte PDFs a texto y tablas, y los
trocea respetando estructura, para poder revisar la calidad antes de
invertir en embeddings o en dependencias mas pesadas. No genera
embeddings, no modifica prompts, reglas clinicas, casos Gold ni la cola
SFT. Los PDFs originales y el texto extraido nunca se copian a un
directorio versionado en Git: todo vive bajo datasets/private/, que
esta excluido de Git (evita problemas de licencia con bibliografia con
copyright).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "datasets" / "private" / "optimus_biblioteca_v1"

TARGET_CHARS = 1800  # aprox. 400 tokens en español (heurística simple)
OVERLAP_CHARS = 270  # ~15% de solape
MIN_CHUNK_CHARS = 200
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_oversized(text: str, limit: int) -> list[str]:
    """Parte un parrafo demasiado largo en frases, respetando el limite.

    pdfplumber no siempre conserva saltos de linea en blanco entre
    parrafos (a veces una pagina entera sale como un solo bloque), asi
    que no basta con dividir por lineas en blanco: hace falta este
    respaldo por frases para que ningun fragmento supere el objetivo de
    tamaño el solo. Funcion pura, facil de probar con texto sintetico.
    """
    if len(text) <= limit:
        return [text]
    piezas: list[str] = []
    actual = ""
    for frase in SENTENCE_SPLIT_RE.split(text):
        if actual and len(actual) + len(frase) + 1 > limit:
            piezas.append(actual.strip())
            actual = frase
        else:
            actual = f"{actual} {frase}".strip() if actual else frase
    if actual:
        piezas.append(actual.strip())
    return piezas


def stable_id(*parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"bib_{digest}"


def _table_to_text(table: list[list[str | None]]) -> str:
    filas = []
    for fila in table:
        celdas = [str(celda).strip() if celda is not None else "" for celda in fila]
        if any(celdas):
            filas.append(" | ".join(celdas))
    return "\n".join(filas)


_GUION_CORTE_RE = re.compile(r"(\w)-\n(\w)")


def _reunir_guiones_de_corte(text: str) -> str:
    """Recompone palabras partidas por guion de fin de linea (word-wrap).

    pdfplumber conserva el guion de corte tal cual aparece impreso; sin
    esto, palabras como "lesio-\\nnes" quedan separadas y ensucian tanto
    la lectura como el troceado posterior. Solo actua sobre el patron
    letra-guion-salto de linea-letra, para no tocar guiones reales
    (p.ej. en "post-quirurgico").
    """
    return _GUION_CORTE_RE.sub(r"\1\2", text)


def extract_document(pdf_path: Path) -> list[dict]:
    """Extrae texto por parrafo y tablas, con el rango de paginas de origen.

    Devuelve una lista de "unidades" (parrafo o tabla) en orden de lectura,
    cada una con su texto y la pagina donde aparece. No aplica todavia
    ningun troceado por tamaño objetivo.
    """
    unidades: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = _reunir_guiones_de_corte(text)
            for parrafo in re.split(r"\n\s*\n", text):
                parrafo = parrafo.strip()
                if len(parrafo) < 20:
                    continue
                for fragmento in _split_oversized(parrafo, TARGET_CHARS):
                    if len(fragmento) >= 20:
                        unidades.append(
                            {"tipo": "texto", "pagina": page_index, "contenido": fragmento}
                        )
            for tabla in page.extract_tables():
                tabla_texto = _table_to_text(tabla)
                if tabla_texto.strip():
                    unidades.append(
                        {"tipo": "tabla", "pagina": page_index, "contenido": tabla_texto}
                    )
    return unidades


def chunk_units(
    unidades: Iterable[dict],
    target_chars: int = TARGET_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[dict]:
    """Agrupa unidades de texto en chunks por tamaño objetivo, con solape.

    Las tablas nunca se fusionan con texto ni entre si (chunking mixto: un
    tipo de contenido por chunk), para no romper su estructura. Cada chunk
    conserva el rango de paginas que abarca. Funcion pura, sin E/S: se
    puede probar con texto sintetico sin necesitar PDFs reales.
    """
    chunks: list[dict] = []
    buffer_texto: list[str] = []
    buffer_paginas: list[int] = []
    buffer_len = 0

    def flush():
        nonlocal buffer_texto, buffer_paginas, buffer_len
        if not buffer_texto:
            return
        contenido = "\n\n".join(buffer_texto).strip()
        if len(contenido) >= MIN_CHUNK_CHARS:
            chunks.append(
                {
                    "tipo": "texto",
                    "pagina_inicio": min(buffer_paginas),
                    "pagina_fin": max(buffer_paginas),
                    "contenido": contenido,
                }
            )
        buffer_texto = []
        buffer_paginas = []
        buffer_len = 0

    for unidad in unidades:
        if unidad["tipo"] == "tabla":
            flush()
            chunks.append(
                {
                    "tipo": "tabla",
                    "pagina_inicio": unidad["pagina"],
                    "pagina_fin": unidad["pagina"],
                    "contenido": unidad["contenido"],
                }
            )
            continue

        parrafo = unidad["contenido"]
        if buffer_len + len(parrafo) > target_chars and buffer_texto:
            flush_content = "\n\n".join(buffer_texto)
            flush()
            # Solape: retiene la cola del chunk anterior como inicio del siguiente.
            cola = flush_content[-overlap_chars:] if overlap_chars else ""
            if cola:
                buffer_texto = [cola]
                buffer_paginas = [unidad["pagina"]]
                buffer_len = len(cola)
        buffer_texto.append(parrafo)
        buffer_paginas.append(unidad["pagina"])
        buffer_len += len(parrafo)

    flush()
    return chunks


def build_document_chunks(pdf_path: Path, region: str) -> list[dict]:
    unidades = extract_document(pdf_path)
    chunks = chunk_units(unidades)
    registros = []
    for indice, chunk in enumerate(chunks):
        registros.append(
            {
                "chunk_id": stable_id(pdf_path.name, str(indice), chunk["contenido"][:80]),
                "region": region,
                "documento_fuente": pdf_path.name,
                "pagina_inicio": chunk["pagina_inicio"],
                "pagina_fin": chunk["pagina_fin"],
                "tipo": chunk["tipo"],
                "contenido": chunk["contenido"],
                "num_caracteres": len(chunk["contenido"]),
            }
        )
    return registros


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--region", required=True, help="p.ej. rodilla, tobillo_pie")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"No existe el directorio de entrada: {args.input_dir}")

    todos_los_chunks: list[dict] = []
    resumen_por_documento = []
    for pdf_path in sorted(args.input_dir.glob("*.pdf")):
        chunks = build_document_chunks(pdf_path, args.region)
        todos_los_chunks.extend(chunks)
        texto_chunks = [c for c in chunks if c["tipo"] == "texto"]
        tabla_chunks = [c for c in chunks if c["tipo"] == "tabla"]
        resumen_por_documento.append(
            {
                "documento": pdf_path.name,
                "chunks_texto": len(texto_chunks),
                "chunks_tabla": len(tabla_chunks),
                "caracteres_totales": sum(c["num_caracteres"] for c in chunks),
                "caracteres_promedio_chunk_texto": (
                    round(sum(c["num_caracteres"] for c in texto_chunks) / len(texto_chunks), 1)
                    if texto_chunks
                    else 0
                ),
            }
        )

    resumen = {
        "schema_version": "optimus-biblioteca-rag-v1-fase1",
        "region": args.region,
        "documentos_procesados": len(resumen_por_documento),
        "chunks_totales": len(todos_los_chunks),
        "por_documento": resumen_por_documento,
    }

    if not args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(args.output_dir / f"chunks_{args.region}.jsonl", todos_los_chunks)
        (args.output_dir / f"resumen_ingesta_{args.region}.json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
