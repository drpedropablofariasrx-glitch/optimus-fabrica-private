import json
import unittest
from unittest.mock import patch

from test_fabrica_abdomen_characterization import load_app_copy


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _style_row(candidate_id, region="abdomen", report="Informe de ejemplo.", status="approved"):
    return {
        "style_candidate_id": candidate_id,
        "region": region,
        "report": report,
        "source": {},
        "candidate_type": "historical_report",
        "approval_status": status,
        "style_eligible": status == "approved",
        "review_notes": "",
    }


class StyleReferenceSelectionTests(unittest.TestCase):
    """Pruebas directas de la seleccion determinista, sin pasar por HTTP."""

    def setUp(self):
        self.tmpdir, self.mod = load_app_copy()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_returns_none_when_no_approved_examples_for_region(self):
        _write_jsonl(
            self.mod.STYLE_REVIEW_QUEUE,
            [_style_row("style_b", region="abdomen", status="candidate")],
        )

        candidate_id, texto = self.mod._referencia_estilo_para_region("abdomen")

        self.assertIsNone(candidate_id)
        self.assertIsNone(texto)

    def test_ignores_rejected_and_other_regions(self):
        _write_jsonl(
            self.mod.STYLE_REVIEW_QUEUE,
            [
                _style_row("style_a", region="abdomen", report="Descartado.", status="rejected"),
                _style_row("style_b", region="lumbar", report="De otra region.", status="approved"),
            ],
        )

        candidate_id, texto = self.mod._referencia_estilo_para_region("abdomen")

        self.assertIsNone(candidate_id)
        self.assertIsNone(texto)

    def test_selection_is_deterministic_by_candidate_id_not_order_or_date(self):
        # Simula una aprobacion masiva: mismas notas, mismo estado, sin
        # nada mas que el id de contenido para desempatar.
        rows = [
            _style_row("style_zzz", region="abdomen", report="Informe Z."),
            _style_row("style_aaa", region="abdomen", report="Informe A."),
            _style_row("style_mmm", region="abdomen", report="Informe M."),
        ]
        _write_jsonl(self.mod.STYLE_REVIEW_QUEUE, rows)

        candidate_id, texto = self.mod._referencia_estilo_para_region("abdomen")

        self.assertEqual(candidate_id, "style_aaa")
        self.assertEqual(texto, "Informe A.")

    def test_selection_is_stable_across_repeated_calls(self):
        rows = [
            _style_row("style_zzz", region="abdomen", report="Informe Z."),
            _style_row("style_aaa", region="abdomen", report="Informe A."),
        ]
        _write_jsonl(self.mod.STYLE_REVIEW_QUEUE, rows)

        first = self.mod._referencia_estilo_para_region("abdomen")
        second = self.mod._referencia_estilo_para_region("abdomen")

        self.assertEqual(first, second)

    def test_report_is_truncated_at_character_limit(self):
        limite = self.mod.STYLE_REFERENCE_CHAR_LIMIT
        texto_largo = "a" * (limite + 500)
        _write_jsonl(
            self.mod.STYLE_REVIEW_QUEUE,
            [_style_row("style_a", region="abdomen", report=texto_largo)],
        )

        _candidate_id, texto = self.mod._referencia_estilo_para_region("abdomen")

        self.assertLessEqual(len(texto), limite + 1)
        self.assertTrue(texto.endswith("…"))
        self.assertTrue(texto_largo.startswith(texto[:-1]))

    def test_report_under_limit_is_not_altered(self):
        texto_corto = "Informe breve y completo."
        _write_jsonl(
            self.mod.STYLE_REVIEW_QUEUE,
            [_style_row("style_a", region="abdomen", report=texto_corto)],
        )

        _candidate_id, texto = self.mod._referencia_estilo_para_region("abdomen")

        self.assertEqual(texto, texto_corto)

    def test_multiple_references_keep_legacy_example_and_are_bounded(self):
        rows = [
            _style_row("style_zzz", region="abdomen", report="Z" * 2300),
            _style_row("style_aaa", region="abdomen", report="A" * 200),
            _style_row("style_mmm", region="abdomen", report="M" * 900),
        ]
        _write_jsonl(self.mod.STYLE_REVIEW_QUEUE, rows)

        candidate_ids, texto = self.mod._referencias_estilo_para_region("abdomen")

        self.assertEqual(candidate_ids[0], "style_aaa")
        self.assertLessEqual(len(candidate_ids), self.mod.STYLE_REFERENCE_MAX_EXAMPLES)
        self.assertLessEqual(len(texto), self.mod.STYLE_REFERENCE_TOTAL_CHAR_LIMIT)
        self.assertIn("EJEMPLO DE REDACCI", texto)


class StyleReferenceGenerationTests(unittest.TestCase):
    """Pruebas de integracion sobre /generar (proveedor mock, sin red)."""

    def setUp(self):
        self.tmpdir, self.mod = load_app_copy()
        self.client = self.mod.app.test_client()
        _write_jsonl(
            self.mod.STYLE_REVIEW_QUEUE,
            [
                _style_row("style_zzz", region="abdomen", report="Informe Z."),
                _style_row("style_aaa", region="abdomen", report="Informe A, el elegido."),
            ],
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_style_reference_off_by_default_leaves_metadata_untouched(self):
        response = self.client.post(
            "/generar",
            json={"caso": "Dictado bruto de prueba.", "provider": "mock"},
        )
        data = response.get_json()

        self.assertNotIn("error", data)
        self.assertNotIn("style_candidate_id", data["generation_metadata"])

    def test_style_reference_enabled_records_candidate_id_in_metadata(self):
        response = self.client.post(
            "/generar",
            json={
                "caso": "Dictado bruto de prueba.",
                "provider": "mock",
                "use_style_reference": True,
            },
        )
        data = response.get_json()

        self.assertNotIn("error", data)
        self.assertEqual(data["generation_metadata"]["style_candidate_id"], "style_aaa")
        self.assertEqual(data["generation_metadata"]["style_candidate_ids"][0], "style_aaa")

    def test_style_reference_enabled_without_approved_examples_is_silent(self):
        _write_jsonl(self.mod.STYLE_REVIEW_QUEUE, [])

        response = self.client.post(
            "/generar",
            json={
                "caso": "Dictado bruto de prueba.",
                "provider": "mock",
                "use_style_reference": True,
            },
        )
        data = response.get_json()

        self.assertNotIn("error", data)
        self.assertNotIn("style_candidate_id", data["generation_metadata"])

    def test_style_reference_is_prepended_as_reference_not_as_clinical_instruction(self):
        captured = {}

        def fake_generar_informe(caso_bruto, api_key, modelo=None, proveedor=None):
            captured["caso_bruto"] = caso_bruto
            self.mod.LAST_GENERATION_METADATA = {
                "provider": "mock", "model": "mock-radiology", "status": "success",
            }
            return "Informe simulado."

        with patch.object(self.mod, "generar_informe", side_effect=fake_generar_informe):
            response = self.client.post(
                "/generar",
                json={
                    "caso": "Dictado bruto de prueba.",
                    "provider": "mock",
                    "use_style_reference": True,
                },
            )

        self.assertNotIn("error", response.get_json())
        caso_enviado = captured["caso_bruto"]
        self.assertIn("REFERENCIA DE ESTILO", caso_enviado)
        self.assertIn("NUNCA como instrucción clínica", caso_enviado)
        self.assertIn("Informe A, el elegido.", caso_enviado)
        self.assertIn("CASO A INFORMAR:", caso_enviado)
        self.assertIn("Dictado bruto de prueba.", caso_enviado)
        # El bloque de referencia debe ir antes del caso real, nunca despues.
        self.assertLess(
            caso_enviado.index("REFERENCIA DE ESTILO"),
            caso_enviado.index("Dictado bruto de prueba."),
        )

    def test_style_reference_off_does_not_alter_case_text(self):
        captured = {}

        def fake_generar_informe(caso_bruto, api_key, modelo=None, proveedor=None):
            captured["caso_bruto"] = caso_bruto
            self.mod.LAST_GENERATION_METADATA = {
                "provider": "mock", "model": "mock-radiology", "status": "success",
            }
            return "Informe simulado."

        with patch.object(self.mod, "generar_informe", side_effect=fake_generar_informe):
            self.client.post(
                "/generar",
                json={"caso": "Dictado bruto de prueba.", "provider": "mock"},
            )

        self.assertEqual(captured["caso_bruto"], "Dictado bruto de prueba.")


class StyleReferencePersistenceTests(unittest.TestCase):
    """El style_candidate_id debe sobrevivir el filtro de generation_metadata."""

    def setUp(self):
        self.tmpdir, self.mod = load_app_copy()
        self.client = self.mod.app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_style_candidate_id_survives_persistence_allowlist(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "Dictado bruto de prueba.",
                "informe_ia": "Informe generado.",
                "informe_final": "Informe generado.",
                "provider": "mock",
                "model": "mock-radiology",
                "generation_metadata": {
                    "provider": "mock",
                    "model": "mock-radiology",
                    "status": "success",
                    "style_candidate_id": "style_aaa",
                },
            },
        )
        data = response.get_json()
        self.assertEqual(response.status_code, 200)

        archivo = self.mod.CASOS_DIR / f"{data['archivo']}.json"
        registro = json.loads(archivo.read_text(encoding="utf-8"))

        self.assertEqual(
            registro["generation_metadata"]["style_candidate_id"], "style_aaa"
        )

    def test_style_candidate_ids_survive_persistence_allowlist(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "Dictado bruto de prueba.",
                "informe_ia": "Informe generado.",
                "informe_final": "Informe generado.",
                "provider": "mock",
                "model": "mock-radiology",
                "generation_metadata": {
                    "provider": "mock",
                    "model": "mock-radiology",
                    "status": "success",
                    "style_candidate_ids": ["style_aaa", "style_bbb"],
                },
            },
        )
        data = response.get_json()
        archivo = self.mod.CASOS_DIR / f"{data['archivo']}.json"
        registro = json.loads(archivo.read_text(encoding="utf-8"))

        self.assertEqual(
            registro["generation_metadata"]["style_candidate_ids"],
            ["style_aaa", "style_bbb"],
        )

    def test_no_style_candidate_id_when_reference_was_not_used(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "Dictado bruto de prueba.",
                "informe_ia": "Informe generado.",
                "informe_final": "Informe generado.",
                "provider": "mock",
                "model": "mock-radiology",
                "generation_metadata": {
                    "provider": "mock",
                    "model": "mock-radiology",
                    "status": "success",
                },
            },
        )
        data = response.get_json()
        self.assertEqual(response.status_code, 200)

        archivo = self.mod.CASOS_DIR / f"{data['archivo']}.json"
        registro = json.loads(archivo.read_text(encoding="utf-8"))

        self.assertNotIn("style_candidate_id", registro.get("generation_metadata", {}))


if __name__ == "__main__":
    unittest.main()
