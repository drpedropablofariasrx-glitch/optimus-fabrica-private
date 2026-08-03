import unittest

from test_fabrica_abdomen_characterization import load_app_copy


class PacsPlainFormatTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir, self.mod = load_app_copy()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_normalizer_removes_markdown_bullets_and_numbered_headers(self):
        raw = (
            "1. **Datos clínicos:**\nCervicalgia.\n\n"
            "3. **Hallazgos:**\n- **C5-C6:** protrusión.\n\n"
            "4. **Impresión diagnóstica:**\n- Estenosis foraminal."
        )

        report = self.mod.normalizar_formato_pacs(raw)

        self.assertEqual(
            report,
            "Datos clínicos:\nCervicalgia.\n\n"
            "Hallazgos:\nC5-C6: protrusión.\n\n"
            "Impresión diagnóstica:\nEstenosis foraminal.",
        )

    def test_cervical_normalizer_removes_quality_section(self):
        raw = (
            "Hallazgos:\nC5-C6: protrusión.\n\n"
            "Análisis de calidad / oportunidades de mejora:\n"
            "Comentario interno que no debe llegar al PACS."
        )

        report = self.mod.normalizar_formato_pacs(raw, eliminar_analisis_calidad=True)

        self.assertEqual(report, "Hallazgos:\nC5-C6: protrusión.")

    def test_cervical_prompt_requires_plain_pacs_output(self):
        prompt = self.mod.load_region_prompt("cervical").lower()

        self.assertIn("texto plano", prompt)
        self.assertIn("no uses markdown", prompt)
        self.assertIn("nunca se muestra como", prompt)
        self.assertNotIn("5. análisis de calidad", prompt)

    def test_main_page_uses_an_editable_plain_text_report_card(self):
        page = self.mod.PAGINA

        self.assertIn('class="report-card"', page)
        self.assertIn('id="informe" class="report-editor"', page)
        self.assertIn("Informe listo para PACS", page)
        self.assertIn("⧉ Copiar", page)
        self.assertIn("function textoInforme()", page)
        self.assertIn("!String(d.informe||'').trim()", page)

    def test_style_rules_are_available_from_a_collapsed_advanced_panel(self):
        page = self.mod.PAGINA

        self.assertIn('id="advancedToggle"', page)
        self.assertIn("Estilo y reglas", page)
        self.assertIn('id="adminText"', page)
        self.assertIn("function toggleAdminPanel()", page)
        self.assertIn("function setAdminPanel(open)", page)
        self.assertIn("Enviar propuesta", page)
        self.assertIn("Aplicar cambio", page)

    def test_main_page_detects_region_from_pasted_text_and_can_analyze_a_report(self):
        page = self.mod.PAGINA

        self.assertIn("function detectarRegionPegada()", page)
        self.assertIn("function programarDeteccionRegion()", page)
        self.assertIn("function analizarInformePegado()", page)
        self.assertIn('id="analyze"', page)
        self.assertIn("Informe pegado", page)
        self.assertIn("validacion_local", page)

    def test_narrow_layout_uses_a_collapsible_configuration_sidebar(self):
        page = self.mod.PAGINA

        self.assertIn("@media(max-width:980px)", page)
        self.assertIn('id="sidebarToggle"', page)
        self.assertIn('class="sidebar-scrim"', page)
        self.assertIn("function toggleSidebar()", page)

    def test_composer_has_a_quick_model_selector_synced_with_configuration(self):
        page = self.mod.PAGINA

        self.assertIn("quick.id='quickModel'", page)
        self.assertIn("function cambiarModeloRapido()", page)
        self.assertIn("function sincronizarSelectorRapidoModelo()", page)
        self.assertIn("MODELOS_BASE_POR_PROVEEDOR", page)
        self.assertIn("modelosDisponiblesProveedor()", page)


if __name__ == "__main__":
    unittest.main()
