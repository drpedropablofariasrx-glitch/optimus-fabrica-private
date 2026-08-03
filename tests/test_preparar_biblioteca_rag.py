import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preparar_biblioteca_rag.py"
SPEC = importlib.util.spec_from_file_location("preparar_biblioteca_rag", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ReunirGuionesDeCorteTests(unittest.TestCase):
    def test_rejoins_word_wrapped_across_line_break(self):
        texto = "el manejo de las lesio-\nnes meniscales"
        self.assertEqual(
            MODULE._reunir_guiones_de_corte(texto),
            "el manejo de las lesiones meniscales",
        )

    def test_does_not_touch_real_hyphens_within_a_line(self):
        texto = "control postquirurgico post-quirurgico sin cambios"
        self.assertEqual(MODULE._reunir_guiones_de_corte(texto), texto)

    def test_does_not_touch_hyphen_at_end_of_line_before_non_word(self):
        texto = "una lista:\n- primer punto"
        self.assertEqual(MODULE._reunir_guiones_de_corte(texto), texto)


class SplitOversizedTests(unittest.TestCase):
    def test_short_text_is_returned_whole(self):
        texto = "Una frase corta. Otra frase corta."
        self.assertEqual(MODULE._split_oversized(texto, limit=200), [texto])

    def test_long_text_is_split_at_sentence_boundaries(self):
        frases = [f"Frase numero {i} con algo de contenido de relleno." for i in range(20)]
        texto = " ".join(frases)

        piezas = MODULE._split_oversized(texto, limit=150)

        self.assertGreater(len(piezas), 1)
        for pieza in piezas:
            self.assertLessEqual(len(pieza), 150 + 60)  # margen: una frase puede exceder el limite ella sola
        # No se pierde contenido: cada frase original aparece en alguna pieza.
        reconstruido = " ".join(piezas)
        for frase in frases:
            self.assertIn(frase, reconstruido)

    def test_single_sentence_longer_than_limit_is_kept_whole(self):
        frase_larga = "Palabra " * 100 + "."
        piezas = MODULE._split_oversized(frase_larga, limit=50)
        self.assertEqual(piezas, [frase_larga])


class ChunkUnitsTests(unittest.TestCase):
    def test_groups_small_paragraphs_up_to_target_size(self):
        unidades = [
            {"tipo": "texto", "pagina": 1, "contenido": "a" * 100},
            {"tipo": "texto", "pagina": 1, "contenido": "b" * 100},
            {"tipo": "texto", "pagina": 2, "contenido": "c" * 100},
        ]

        chunks = MODULE.chunk_units(unidades, target_chars=500, overlap_chars=0)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["pagina_inicio"], 1)
        self.assertEqual(chunks[0]["pagina_fin"], 2)

    def test_splits_into_multiple_chunks_when_exceeding_target(self):
        unidades = [
            {"tipo": "texto", "pagina": 1, "contenido": "a" * 300},
            {"tipo": "texto", "pagina": 1, "contenido": "b" * 300},
            {"tipo": "texto", "pagina": 2, "contenido": "c" * 300},
        ]

        chunks = MODULE.chunk_units(unidades, target_chars=400, overlap_chars=0)

        self.assertGreaterEqual(len(chunks), 2)

    def test_tables_are_never_merged_with_text_or_each_other(self):
        unidades = [
            {"tipo": "texto", "pagina": 1, "contenido": "texto antes de la tabla " * 15},
            {"tipo": "tabla", "pagina": 1, "contenido": "col1 | col2\nval1 | val2"},
            {"tipo": "tabla", "pagina": 1, "contenido": "colA | colB\nvalA | valB"},
            {"tipo": "texto", "pagina": 2, "contenido": "texto despues de la tabla " * 15},
        ]

        chunks = MODULE.chunk_units(unidades, target_chars=1800, overlap_chars=0)

        tipos = [c["tipo"] for c in chunks]
        self.assertEqual(tipos, ["texto", "tabla", "tabla", "texto"])

    def test_discards_fragments_below_minimum_size(self):
        unidades = [{"tipo": "texto", "pagina": 1, "contenido": "muy corto"}]

        chunks = MODULE.chunk_units(unidades, target_chars=1800, overlap_chars=0)

        self.assertEqual(chunks, [])

    def test_overlap_carries_tail_of_previous_chunk_into_next(self):
        unidades = [
            {"tipo": "texto", "pagina": 1, "contenido": "x" * 300},
            {"tipo": "texto", "pagina": 1, "contenido": "y" * 300},
        ]

        chunks = MODULE.chunk_units(unidades, target_chars=350, overlap_chars=50)

        self.assertEqual(len(chunks), 2)
        cola_primero = chunks[0]["contenido"][-50:]
        self.assertIn(cola_primero, chunks[1]["contenido"])


class BuildDocumentChunksIdsTests(unittest.TestCase):
    def test_stable_id_is_deterministic_and_prefixed(self):
        a = MODULE.stable_id("doc.pdf", "0", "contenido de ejemplo")
        b = MODULE.stable_id("doc.pdf", "0", "contenido de ejemplo")
        c = MODULE.stable_id("doc.pdf", "1", "contenido de ejemplo")

        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("bib_"))


if __name__ == "__main__":
    unittest.main()
