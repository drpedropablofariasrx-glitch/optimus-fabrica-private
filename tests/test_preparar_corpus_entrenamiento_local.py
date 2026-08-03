import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preparar_corpus_entrenamiento_local.py"
SPEC = importlib.util.spec_from_file_location("corpus_entrenamiento", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def style_row(region="rodilla", report="Datos clínicos: dolor\n\nExploración: RM rodilla\n\nHallazgos:\nNormal.\n\nImpresión diagnóstica:\nNormal."):
    return {"region": region, "report": report, "approval_status": "approved"}


def sft_row(case_id, region="rodilla", modality="RM", raw="Dictado de prueba", final="Informe final de prueba"):
    return {
        "review_case_id": case_id,
        "region": region,
        "modality": modality,
        "raw_input": raw,
        "final_report": final,
        "approval_status": "approved",
        "sft_eligible": True,
        "source": {"file": "ficticio.txt", "lines": [1, 4]},
    }


class LocalTrainingCorpusTests(unittest.TestCase):
    def test_builds_disjoint_train_and_benchmark_and_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            style = base / "style.jsonl"
            sft = base / "sft.jsonl"
            write_jsonl(style, [style_row()])
            write_jsonl(sft, [sft_row(str(index), raw=f"Dictado {index}", final=f"Informe {index}") for index in range(10)])

            train, benchmark, manifest = MODULE.build(style, [sft])

        self.assertEqual(len(train) + len(benchmark), 10)
        self.assertEqual(len(benchmark), 2)
        self.assertFalse({row["training_pair_id"] for row in train} & {row["training_pair_id"] for row in benchmark})
        self.assertTrue(manifest["safety"]["train_and_benchmark_disjoint"])
        self.assertIn("rodilla|RM", manifest["style_profiles"]["profiles_by_region_modality"])
        self.assertEqual(train[0]["messages"][2]["role"], "assistant")
        self.assertEqual(train[0]["candidate_type"], "unknown")

    def test_keeps_small_regions_out_of_benchmark(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            style = base / "style.jsonl"
            sft = base / "sft.jsonl"
            write_jsonl(style, [style_row(region="codo")])
            write_jsonl(sft, [sft_row(str(index), region="codo") for index in range(3)])

            train, benchmark, _manifest = MODULE.build(style, [sft])

        self.assertEqual(len(train), 3)
        self.assertEqual(benchmark, [])

    def test_excludes_unapproved_and_possible_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            style = base / "style.jsonl"
            sft = base / "sft.jsonl"
            rejected = sft_row("bad", raw="NHC: 123456789", final="Informe")
            rejected["approval_status"] = "approved"
            ineligible = sft_row("no", raw="dato", final="informe")
            ineligible["sft_eligible"] = False
            write_jsonl(style, [style_row()])
            write_jsonl(sft, [rejected, ineligible])

            train, benchmark, manifest = MODULE.build(style, [sft])

        self.assertEqual(train, [])
        self.assertEqual(benchmark, [])
        self.assertEqual(manifest["sft"]["discarded"]["possible_identifier"], 1)
        self.assertEqual(manifest["sft"]["discarded"]["not_approved_or_ineligible"], 1)

    def test_cli_outputs_private_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            style = base / "style.jsonl"
            sft = base / "sft.jsonl"
            output = base / "out"
            write_jsonl(style, [style_row()])
            write_jsonl(sft, [sft_row(str(index), raw=f"d{index}", final=f"i{index}") for index in range(8)])
            train, benchmark, manifest = MODULE.build(style, [sft])
            MODULE.write_jsonl(output / "sft_train.jsonl", train)
            MODULE.write_jsonl(output / "benchmark_holdout.jsonl", benchmark)
            (output / "manifiesto_corpus.json").write_text(json.dumps(manifest), encoding="utf-8")

            self.assertTrue((output / "sft_train.jsonl").exists())
            self.assertTrue((output / "benchmark_holdout.jsonl").exists())
            self.assertTrue((output / "manifiesto_corpus.json").exists())


if __name__ == "__main__":
    unittest.main()
