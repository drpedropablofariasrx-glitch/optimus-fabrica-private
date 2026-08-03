"""Biblioteca RAG local de OPTIMUS: recuperacion de bibliografia por region.

Fase 2: embeddings locales (BGE-M3) y busqueda por similitud, todavia sin
integracion con Flask ni con la generacion de informes. No modifica
prompts, reglas clinicas, casos Gold ni la cola SFT. El indice y los
embeddings viven en datasets/private/, excluido de Git.

Con un corpus de decenas de documentos (miles de chunks como mucho), una
busqueda por fuerza bruta en memoria con numpy es instantanea: no hace
falta un indice ANN (tipo sqlite-vec) hasta que el corpus crezca varios
ordenes de magnitud. Si eso pasa, esta funcion es el unico sitio a
cambiar.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_DIR = ROOT / "datasets" / "private" / "optimus_biblioteca_v1"
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"

_modelo = None


def _cargar_modelo():
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer

        _modelo = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _modelo


def _leer_chunks(chunks_paths: Iterable[Path]) -> list[dict]:
    filas = []
    for path in chunks_paths:
        if not path.exists():
            continue
        for linea in path.read_text(encoding="utf-8").splitlines():
            if linea.strip():
                filas.append(json.loads(linea))
    return filas


def construir_indice(index_dir: Path = DEFAULT_INDEX_DIR) -> dict:
    """Genera embeddings para todos los chunks_*.jsonl en index_dir.

    Guarda embeddings.npy (N x dim, normalizados) y metadatos.jsonl (una
    fila por embedding, mismo orden). Devuelve un resumen, sin exponer
    contenido.
    """
    chunks_paths = sorted(index_dir.glob("chunks_*.jsonl"))
    filas = _leer_chunks(chunks_paths)
    if not filas:
        raise SystemExit(f"No se encontraron chunks_*.jsonl en {index_dir}")

    modelo = _cargar_modelo()
    textos = [fila["contenido"] for fila in filas]
    embeddings = modelo.encode(
        textos,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=16,
    )
    embeddings = np.asarray(embeddings, dtype=np.float32)

    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "embeddings.npy", embeddings)
    metadatos_path = index_dir / "metadatos.jsonl"
    metadatos_path.write_text(
        "".join(
            json.dumps(
                {k: fila[k] for k in (
                    "chunk_id", "region", "documento_fuente",
                    "pagina_inicio", "pagina_fin", "tipo", "contenido",
                )},
                ensure_ascii=False,
            )
            + "\n"
            for fila in filas
        ),
        encoding="utf-8",
    )
    return {
        "chunks_indexados": len(filas),
        "dimension_embedding": int(embeddings.shape[1]),
        "archivos_fuente": [p.name for p in chunks_paths],
    }


_embeddings_cache: np.ndarray | None = None
_metadatos_cache: list[dict] | None = None


def _cargar_indice(index_dir: Path = DEFAULT_INDEX_DIR) -> tuple[np.ndarray, list[dict]]:
    global _embeddings_cache, _metadatos_cache
    if _embeddings_cache is None or _metadatos_cache is None:
        embeddings_path = index_dir / "embeddings.npy"
        metadatos_path = index_dir / "metadatos.jsonl"
        if not embeddings_path.exists() or not metadatos_path.exists():
            raise SystemExit(
                f"No hay indice en {index_dir}. Corre construir_indice() primero."
            )
        _embeddings_cache = np.load(embeddings_path)
        _metadatos_cache = [
            json.loads(linea)
            for linea in metadatos_path.read_text(encoding="utf-8").splitlines()
            if linea.strip()
        ]
    return _embeddings_cache, _metadatos_cache


def buscar_bibliografia(
    query: str,
    region: str | None = None,
    top_k: int = 5,
    index_dir: Path = DEFAULT_INDEX_DIR,
) -> list[dict]:
    """Busca los chunks mas relevantes para query (opcionalmente por region).

    Devuelve una lista de hasta top_k dicts con chunk_id, region,
    documento_fuente, pagina_inicio, pagina_fin, tipo, contenido y score
    (similitud coseno, ya que los embeddings estan normalizados).
    """
    embeddings, metadatos = _cargar_indice(index_dir)
    modelo = _cargar_modelo()
    query_embedding = modelo.encode([query], normalize_embeddings=True)[0]

    if region is not None:
        indices = [i for i, fila in enumerate(metadatos) if fila.get("region") == region]
    else:
        indices = list(range(len(metadatos)))
    if not indices:
        return []

    subset = embeddings[indices]
    scores = subset @ query_embedding
    orden = np.argsort(-scores)[:top_k]

    resultados = []
    for pos in orden:
        idx_original = indices[pos]
        fila = dict(metadatos[idx_original])
        fila["score"] = float(scores[pos])
        resultados.append(fila)
    return resultados
