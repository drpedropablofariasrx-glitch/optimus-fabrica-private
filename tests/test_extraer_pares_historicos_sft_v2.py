import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extraer_pares_historicos_sft_v2.py"
SPEC = importlib.util.spec_from_file_location("extractor_sft_v2", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


RAW = """Datos clínicos: dolor abdominal

Exploración: TC abdomen y pelvis

Hallazgos:
Hígado conservado. Lesión quística renal izquierda sin componente sólido.

Impresión diagnóstica:
"""

FINAL = """**Datos clínicos:** dolor abdominal

**Exploración:** TC abdomen y pelvis

**Hallazgos:**
Hígado conservado. Lesión quística renal izquierda sin componente sólido.

**Impresión diagnóstica:**
Quiste renal izquierdo sin signos de agresividad.

Interpretación global:
Este texto no forma parte del informe final.
"""


class ExtractorSftV2Tests(unittest.TestCase):
    def test_recognizes_markdown_and_builds_high_confidence_pair(self):
        text = RAW + "\n" + FINAL
        blocks = MODULE.parse_report_blocks(text, "Abdomen y pelvis.txt", "abdomen_pelvis")
        groups = MODULE.group_blocks(blocks)
        pair = MODULE.pair_from_group(groups[0], text)

        self.assertEqual(len(blocks), 2)
        self.assertEqual(len(groups), 1)
        self.assertEqual(pair["approval_status"], "pending")
        self.assertEqual(pair["modality"], "TC")
        self.assertNotIn("Interpretación global", pair["final_report"])
        self.assertFalse(pair["sft_eligible"])

    def test_does_not_group_adjacent_different_cases(self):
        other = FINAL.replace("dolor abdominal", "hemoptisis").replace(
            "TC abdomen y pelvis", "AngioTC de arterias pulmonares"
        ).replace("Hígado conservado", "Enfisema pulmonar severo")
        blocks = MODULE.parse_report_blocks(RAW + "\n" + other, "Torax.txt", "torax")

        self.assertEqual(len(MODULE.group_blocks(blocks)), 2)

    def test_sanitizes_identifiers_and_dates(self):
        value = MODULE.sanitize(
            "NHC: 123456789\nControl del 12/03/2025. Contacto a@b.com."
        )

        self.assertNotIn("123456789", value)
        self.assertIn("[FECHA]", value)
        self.assertIn("[EMAIL]", value)

    def test_removes_dataset_metadata_after_impression(self):
        final_with_metadata = FINAL.replace(
            "Interpretación global:", "Nota: DATASET_ENTRY no visible\nInterpretación global:"
        )
        blocks = MODULE.parse_report_blocks(
            RAW + "\n" + final_with_metadata,
            "Abdomen y pelvis.txt",
            "abdomen_pelvis",
        )

        self.assertNotIn("DATASET_ENTRY", blocks[-1].report_text)

    def test_merge_preserves_reviewed_rows_and_does_not_autoapprove(self):
        previous = {
            "review_case_id": "reviewed_1",
            "region": "abdomen_pelvis",
            "source": {"file": "old.txt", "lines": [1, 10]},
            "raw_input": "entrada revisada",
            "final_report": "informe revisado",
            "approval_status": "approved",
            "review_notes": "confirmado",
            "sft_eligible": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Abdomen y pelvis.txt"
            source.write_text(RAW + "\n" + FINAL, encoding="utf-8")
            merged, episodes, summary = MODULE.build_dataset(
                [(source, "abdomen_pelvis")], [previous]
            )

        self.assertEqual(merged[0], previous)
        self.assertEqual(summary["previous_review_rows_preserved"], 1)
        self.assertEqual(len(episodes), 1)
        self.assertTrue(all(row["approval_status"] != "approved" for row in merged[1:]))

    def test_jsonl_writer_is_atomic_and_roundtrips_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "queue.jsonl"
            MODULE.write_jsonl(target, [{"texto": "muñeca"}])
            row = json.loads(target.read_text(encoding="utf-8"))

        self.assertEqual(row["texto"], "muñeca")


if __name__ == "__main__":
    unittest.main()
