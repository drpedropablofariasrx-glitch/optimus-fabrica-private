import sys
import unittest
from pathlib import Path
from unittest.mock import patch

APP_DIR = Path(__file__).resolve().parents[1] / "00_APP"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import rag_biblioteca  # noqa: E402  (necesita APP_DIR en sys.path)
from test_fabrica_abdomen_characterization import load_app_copy  # noqa: E402


def _resultado(chunk_id, documento="doc.pdf", pagina=1, contenido="Texto de ejemplo.", score=0.8):
    return {
        "chunk_id": chunk_id,
        "region": "rodilla",
        "documento_fuente": documento,
        "pagina_inicio": pagina,
        "pagina_fin": pagina,
        "tipo": "texto",
        "contenido": contenido,
        "score": score,
    }


class ReferenciaBibliografiaParaCasoTests(unittest.TestCase):
    """Pruebas directas de la funcion pura, mockeando la busqueda real."""

    def setUp(self):
        self.tmpdir, self.mod = load_app_copy()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_returns_empty_when_no_results(self):
        with patch.object(rag_biblioteca, "buscar_bibliografia", return_value=[]):
            usados, bloque = self.mod._referencia_bibliografia_para_caso("dictado", "rodilla")
        self.assertEqual(usados, [])
        self.assertEqual(bloque, "")

    def test_returns_empty_when_module_raises_system_exit(self):
        def _raise(*args, **kwargs):
            raise SystemExit("no hay indice")

        with patch.object(rag_biblioteca, "buscar_bibliografia", side_effect=_raise):
            usados, bloque = self.mod._referencia_bibliografia_para_caso("dictado", "rodilla")
        self.assertEqual(usados, [])
        self.assertEqual(bloque, "")

    def test_returns_empty_on_unexpected_error_without_raising(self):
        with patch.object(rag_biblioteca, "buscar_bibliografia", side_effect=RuntimeError("boom")):
            usados, bloque = self.mod._referencia_bibliografia_para_caso("dictado", "rodilla")
        self.assertEqual(usados, [])
        self.assertEqual(bloque, "")

    def test_collects_chunk_ids_and_citation_in_order(self):
        resultados = [
            _resultado("bib_a", documento="uno.pdf", pagina=3, contenido="Contenido A."),
            _resultado("bib_b", documento="dos.pdf", pagina=7, contenido="Contenido B."),
        ]
        with patch.object(rag_biblioteca, "buscar_bibliografia", return_value=resultados):
            usados, bloque = self.mod._referencia_bibliografia_para_caso("dictado", "rodilla")

        self.assertEqual(usados, ["bib_a", "bib_b"])
        self.assertIn("uno.pdf, pág. 3", bloque)
        self.assertIn("Contenido A.", bloque)
        self.assertIn("dos.pdf, pág. 7", bloque)
        self.assertIn("Contenido B.", bloque)

    def test_respects_max_chunks_constant(self):
        resultados = [
            _resultado(f"bib_{i}", contenido=f"Contenido {i}.")
            for i in range(self.mod.BIBLIOGRAFIA_MAX_CHUNKS + 5)
        ]
        with patch.object(rag_biblioteca, "buscar_bibliografia", return_value=resultados) as mocked:
            self.mod._referencia_bibliografia_para_caso("dictado", "rodilla")
        _args, kwargs = mocked.call_args
        self.assertEqual(kwargs.get("top_k"), self.mod.BIBLIOGRAFIA_MAX_CHUNKS)

    def test_truncates_long_chunk_to_per_chunk_limit(self):
        limite = self.mod.BIBLIOGRAFIA_PER_CHUNK_CHAR_LIMIT
        resultados = [_resultado("bib_a", contenido="x" * (limite + 500))]
        with patch.object(rag_biblioteca, "buscar_bibliografia", return_value=resultados):
            _usados, bloque = self.mod._referencia_bibliografia_para_caso("dictado", "rodilla")
        # el bloque incluye la cita ademas del contenido, asi que se compara
        # solo la parte de contenido recortada.
        contenido_incluido = bloque.split("\n", 1)[1]
        self.assertLessEqual(len(contenido_incluido), limite + 1)
        self.assertTrue(contenido_incluido.endswith("…"))

    def test_stops_once_total_char_budget_is_exhausted(self):
        # Cada chunk se recorta al limite por-chunk, asi que hacen falta
        # varios chunks grandes (no uno solo) para agotar el presupuesto
        # total y comprobar que uno adicional se queda fuera.
        limite_por_chunk = self.mod.BIBLIOGRAFIA_PER_CHUNK_CHAR_LIMIT
        grandes = [
            _resultado(f"bib_grande_{i}", contenido="y" * limite_por_chunk)
            for i in range(10)
        ]
        resultados = grandes + [_resultado("bib_extra", contenido="z" * 50)]
        with patch.object(rag_biblioteca, "buscar_bibliografia", return_value=resultados):
            usados, _bloque = self.mod._referencia_bibliografia_para_caso("dictado", "rodilla")
        self.assertNotIn("bib_extra", usados)


class GenerarConBibliografiaTests(unittest.TestCase):
    """Pruebas de integracion sobre /generar (proveedor mock, sin red)."""

    def setUp(self):
        self.tmpdir, self.mod = load_app_copy()
        self.client = self.mod.app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_bibliografia_off_leaves_metadata_untouched(self):
        response = self.client.post(
            "/generar",
            json={"caso": "Dictado de prueba.", "provider": "mock"},
        )
        data = response.get_json()
        self.assertNotIn("error", data)
        self.assertNotIn("bibliografia_chunk_ids", data["generation_metadata"])

    def test_bibliografia_on_without_index_is_silent(self):
        # Sin mockear rag_biblioteca: en el entorno de pruebas no hay
        # indice construido, asi que debe degradar sin romper la
        # generacion (igual que la referencia de estilo sin aprobados).
        response = self.client.post(
            "/generar",
            json={"caso": "Dictado de prueba.", "provider": "mock", "use_bibliografia": True},
        )
        data = response.get_json()
        self.assertNotIn("error", data)
        self.assertNotIn("bibliografia_chunk_ids", data["generation_metadata"])

    def test_bibliografia_on_with_results_records_ids_and_injects_reference(self):
        captured = {}

        def fake_generar_informe(caso_bruto, api_key, modelo=None, proveedor=None):
            captured["caso_bruto"] = caso_bruto
            self.mod.LAST_GENERATION_METADATA = {
                "provider": "mock", "model": "mock-radiology", "status": "success",
            }
            return "Informe simulado."

        resultados = [_resultado("bib_x", documento="guia.pdf", pagina=9, contenido="Dato clinico general.")]
        with patch.object(rag_biblioteca, "buscar_bibliografia", return_value=resultados), \
             patch.object(self.mod, "generar_informe", side_effect=fake_generar_informe):
            response = self.client.post(
                "/generar",
                json={"caso": "Dictado de prueba.", "provider": "mock", "use_bibliografia": True},
            )

        data = response.get_json()
        self.assertNotIn("error", data)
        self.assertEqual(data["generation_metadata"]["bibliografia_chunk_ids"], ["bib_x"])

        caso_enviado = captured["caso_bruto"]
        self.assertIn("REFERENCIA BIBLIOGRÁFICA", caso_enviado)
        self.assertIn("NUNCA los uses como fuente de", caso_enviado)
        self.assertIn("Dato clinico general.", caso_enviado)
        self.assertIn("Dictado de prueba.", caso_enviado)
        self.assertLess(
            caso_enviado.index("REFERENCIA BIBLIOGRÁFICA"),
            caso_enviado.index("Dictado de prueba."),
        )

    def test_bibliografia_chunk_ids_survive_persistence_allowlist(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "Dictado de prueba.",
                "informe_ia": "Informe generado.",
                "informe_final": "Informe generado.",
                "provider": "mock",
                "model": "mock-radiology",
                "generation_metadata": {
                    "provider": "mock",
                    "model": "mock-radiology",
                    "status": "success",
                    "bibliografia_chunk_ids": ["bib_x", "bib_y"],
                },
            },
        )
        data = response.get_json()
        self.assertEqual(response.status_code, 200)

        import json
        archivo = self.mod.CASOS_DIR / f"{data['archivo']}.json"
        registro = json.loads(archivo.read_text(encoding="utf-8"))
        self.assertEqual(
            registro["generation_metadata"]["bibliografia_chunk_ids"], ["bib_x", "bib_y"]
        )


if __name__ == "__main__":
    unittest.main()
