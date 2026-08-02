import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "importar_conversacion_chatgpt_msk.py"
)
SPEC = importlib.util.spec_from_file_location("importar_chatgpt_msk", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


DRAFT = """Datos clínicos:
Omalgia derecha.

Exploración:
RM de hombro derecho.

Hallazgos:
Tendinosis del supraespinoso. Sin atrofia muscular.

Impresión diagnóstica:
Tendinosis del supraespinoso.

INTERPRETACIÓN GLOBAL
Texto que no pertenece al informe PACS.
"""

CORRECTION = """mi corrección Datos clínicos:
Omalgia derecha.

Exploración:
RM de hombro derecho.

Hallazgos:
Tendinosis del supraespinoso. Sin atrofia significativa ni edema.

Impresión diagnóstica:
Tendinopatía del supraespinoso sin rotura.
Mostrar más
"""

RAW_WITH_EMPTY_IMPRESSION = """Datos clínicos:
Omalgia derecha.

Exploración:
RM de hombro derecho.

Hallazgos:
Tendinosis del supraespinoso sin rotura.

Impresión diagnóstica:
"""

RAW_WITHOUT_IMPRESSION_HEADER = """Datos clínicos:
Omalgia derecha.

Exploración:
RM de hombro derecho.

Hallazgos:
Tendinosis del supraespinoso sin rotura.
"""


class ImportarConversacionChatGPTMSKTests(unittest.TestCase):
    def test_extracts_explicit_draft_correction_pair(self):
        document = {
            "source": {
                "project": "MSK hombro",
                "conversation_title": "Informe MSK Hombro",
                "conversation_id": "conversation-1",
            },
            "messages": [
                {"turn_id": "assistant-1", "role": "assistant", "text": DRAFT},
                {"turn_id": "user-2", "role": "user", "text": CORRECTION},
            ],
        }

        rows = MODULE.extract_correction_pairs(document, "hombro.json")

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["region"], "hombro")
        self.assertEqual(row["modality"], "RM")
        self.assertEqual(row["approval_status"], "candidate")
        self.assertEqual(row["training_task"], "draft_to_corrected_report")
        self.assertFalse(row["sft_eligible"])
        self.assertNotIn("INTERPRETACIÓN GLOBAL", row["raw_input"])
        self.assertNotIn("mi corrección", row["final_report"].lower())
        self.assertNotIn("Mostrar más", row["final_report"])

    def test_ignores_model_report_without_user_correction(self):
        document = {
            "messages": [
                {
                    "turn_id": "user-1",
                    "role": "user",
                    "text": "Artro RM de hombro. Hallazgos: lesión labral.",
                },
                {"turn_id": "assistant-2", "role": "assistant", "text": DRAFT},
            ]
        }

        self.assertEqual(
            MODULE.extract_correction_pairs(document, "hombro.json"),
            [],
        )

    def test_extracts_raw_generated_pair_for_manual_review(self):
        document = {
            "source": {
                "project": "MSK hombro",
                "conversation_title": "Informe MSK Hombro",
                "conversation_id": "conversation-raw",
            },
            "messages": [
                {
                    "turn_id": "user-1",
                    "role": "user",
                    "text": RAW_WITH_EMPTY_IMPRESSION,
                },
                {"turn_id": "assistant-2", "role": "assistant", "text": DRAFT},
            ],
        }

        rows = MODULE.extract_review_pairs(
            document,
            "hombro.json",
            expected_region="hombro",
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["candidate_type"], "chatgpt_raw_generated_pair")
        self.assertEqual(row["approval_status"], "candidate")
        self.assertFalse(row["sft_eligible"])

    def test_accepts_raw_report_without_impression_header(self):
        document = {
            "source": {"conversation_id": "conversation-no-impression"},
            "messages": [
                {
                    "turn_id": "user-1",
                    "role": "user",
                    "text": RAW_WITHOUT_IMPRESSION_HEADER,
                },
                {"turn_id": "assistant-2", "role": "assistant", "text": DRAFT},
            ],
        }

        rows = MODULE.extract_review_pairs(
            document,
            "hombro.json",
            expected_region="hombro",
        )

        self.assertEqual(len(rows), 1)
        self.assertTrue(
            rows[0]["raw_input"].rstrip().endswith("Impresión diagnóstica:")
        )

    def test_prefers_explicit_final_correction_over_generated_draft(self):
        document = {
            "source": {"conversation_id": "conversation-corrected"},
            "messages": [
                {
                    "turn_id": "user-1",
                    "role": "user",
                    "text": RAW_WITH_EMPTY_IMPRESSION,
                },
                {"turn_id": "assistant-2", "role": "assistant", "text": DRAFT},
                {"turn_id": "user-3", "role": "user", "text": CORRECTION},
            ],
        }

        rows = MODULE.extract_review_pairs(
            document,
            "hombro.json",
            expected_region="hombro",
        )

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(
            row["candidate_type"],
            "chatgpt_raw_final_correction_candidate",
        )
        self.assertEqual(row["approval_status"], "pending")
        self.assertEqual(row["source"]["turns"], ["user-1", "assistant-2", "user-3"])
        self.assertIn("Tendinopatía del supraespinoso sin rotura", row["final_report"])

    def test_expected_region_excludes_cross_region_contamination(self):
        lumbar_raw = RAW_WITH_EMPTY_IMPRESSION.replace(
            "Omalgia derecha.",
            "Lumbalgia.",
        ).replace(
            "RM de hombro derecho.",
            "RM lumbar.",
        ).replace(
            "Tendinosis del supraespinoso sin rotura.",
            "Discopatía L4-L5.",
        )
        lumbar_draft = DRAFT.replace("hombro", "columna lumbar").replace(
            "Tendinosis del supraespinoso",
            "Discopatía L4-L5",
        )
        document = {
            "messages": [
                {"turn_id": "user-1", "role": "user", "text": lumbar_raw},
                {"turn_id": "assistant-2", "role": "assistant", "text": lumbar_draft},
            ]
        }

        rows = MODULE.extract_review_pairs(
            document,
            "hombro.json",
            expected_region="hombro",
        )

        self.assertEqual(rows, [])

    def test_sanitizes_direct_identifiers(self):
        text = (
            "Paciente: Ejemplo\n"
            "Edad, genero y hospital: 72, mujer\n"
            "NHC: 123456789\n"
            "SIP 349346\n"
            "Correo: prueba@example.com\n"
            "Datos clínicos: dolor."
        )

        cleaned = MODULE.sanitize_text(text)

        self.assertNotIn("Paciente:", cleaned)
        self.assertNotIn("Edad, genero y hospital:", cleaned)
        self.assertNotIn("NHC:", cleaned)
        self.assertNotIn("349346", cleaned)
        self.assertNotIn("prueba@example.com", cleaned)
        self.assertIn("[EMAIL]", cleaned)

    def test_merge_preserves_existing_rows_and_is_idempotent(self):
        existing = [{"review_case_id": "old", "approval_status": "approved"}]
        candidate = {"review_case_id": "new", "approval_status": "candidate"}

        merged, added = MODULE.merge_rows(existing, [candidate, candidate])

        self.assertEqual(merged[0], existing[0])
        self.assertEqual(added, 1)
        self.assertEqual(len(merged), 2)

    def test_merge_deduplicates_same_conversation_final_turn(self):
        existing = [
            {
                "review_case_id": "old",
                "source": {
                    "conversation_id": "conversation-1",
                    "turns": ["assistant-2", "user-3"],
                },
            }
        ]
        candidate = {
            "review_case_id": "new-hash",
            "source": {
                "conversation_id": "conversation-1",
                "turns": ["user-1", "assistant-2", "user-3"],
            },
        }

        merged, added = MODULE.merge_rows(existing, [candidate])

        self.assertEqual(added, 0)
        self.assertEqual(merged, existing)

    def test_jsonl_writer_roundtrips_utf8(self):
        rows = [{"review_case_id": "uno", "texto": "Impresión diagnóstica"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queue.jsonl"
            MODULE.atomic_write_jsonl(path, rows)
            loaded = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(loaded, rows)


if __name__ == "__main__":
    unittest.main()
