import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "00_APP" / "optimus_app.py"
WRAPPER_SOURCE = ROOT / "00_APP" / "fabrica_abdomen.py"
REGION_SOURCE = ROOT / "01_abdomen"
LUMBAR_SOURCE = ROOT / "02_lumbar"
CERVICAL_SOURCE = ROOT / "03_cervical"
RODILLA_SOURCE = ROOT / "05_rodilla"
MANO_MUNECA_SOURCE = ROOT / "06_mano_muneca"
CODO_SOURCE = ROOT / "07_codo"
TOBILLO_PIE_SOURCE = ROOT / "08_tobillo_pie"
TORAX_SOURCE = ROOT / "04_torax"


def load_app_copy():
    tmpdir = tempfile.TemporaryDirectory()
    tmp_root = Path(tmpdir.name)
    app_dir = tmp_root / "00_APP"
    region_dir = tmp_root / "01_abdomen"
    lumbar_dir = tmp_root / "02_lumbar"
    cervical_dir = tmp_root / "03_cervical"
    rodilla_dir = tmp_root / "05_rodilla"
    mano_muneca_dir = tmp_root / "06_mano_muneca"
    codo_dir = tmp_root / "07_codo"
    tobillo_pie_dir = tmp_root / "08_tobillo_pie"
    torax_dir = tmp_root / "04_torax"
    app_dir.mkdir()
    ignore_cache = shutil.ignore_patterns("__pycache__")
    shutil.copytree(REGION_SOURCE, region_dir, ignore=ignore_cache)
    shutil.copytree(LUMBAR_SOURCE, lumbar_dir, ignore=ignore_cache)
    shutil.copytree(CERVICAL_SOURCE, cervical_dir, ignore=ignore_cache)
    shutil.copytree(RODILLA_SOURCE, rodilla_dir, ignore=ignore_cache)
    shutil.copytree(MANO_MUNECA_SOURCE, mano_muneca_dir, ignore=ignore_cache)
    shutil.copytree(CODO_SOURCE, codo_dir, ignore=ignore_cache)
    shutil.copytree(TOBILLO_PIE_SOURCE, tobillo_pie_dir, ignore=ignore_cache)
    shutil.copytree(TORAX_SOURCE, torax_dir, ignore=ignore_cache)
    shutil.copy2(ROOT / "00_APP" / "region_registry.py", app_dir / "region_registry.py")
    shutil.copy2(ROOT / "00_APP" / "provider_llama_cpp.py", app_dir / "provider_llama_cpp.py")
    app_copy = app_dir / "optimus_app.py"
    shutil.copy2(APP_SOURCE, app_copy)
    shutil.copy2(WRAPPER_SOURCE, app_dir / "fabrica_abdomen.py")
    spec = importlib.util.spec_from_file_location(
        f"fabrica_abdomen_under_test_{id(tmpdir)}", app_copy
    )
    module = importlib.util.module_from_spec(spec)
    old_registry = sys.modules.pop("region_registry", None)
    sys.path.insert(0, str(app_dir))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(app_dir))
        sys.modules.pop("region_registry", None)
        if old_registry is not None:
            sys.modules["region_registry"] = old_registry
    module.app.config.update(TESTING=True)
    return tmpdir, module


LEGACY_PROMPT_ABDOMEN = """Eres un radiólogo experto en TC de abdomen y pelvis. Generas informes
profesionales estructurados a partir del dictado bruto del radiólogo.

FORMATO OBLIGATORIO — SIEMPRE estos bloques, en este orden:

1. Datos clínicos: [en minúsculas; si vacío "No aportados"]
2. Hallazgos: [cada hallazgo en línea independiente, orden anatómico]
3. Impresión diagnóstica: [conclusiones jerarquizadas, sin medidas, sin viñetas, líneas independientes]
4. Interpretación global: [3-6 líneas: hallazgo principal + relevancia clínica]
5. Análisis de oportunidades de mejora: [revisar: estructura según indicación, hallazgos infra/sobreinterpretados,
   terminología precisa (Bosniak/O-RADS/LI-RADS/Fleischner/TNM), cuantificación, seguimiento, inconsistencias]

REGLAS DURAS (formato):
- Números SIEMPRE en cifra, nunca en palabras (44 mm, no "cuarenta y cuatro").
- Porcentajes con símbolo %. Medidas con unidad explícita (mm/cm).
- Datos clínicos en minúsculas.
- No incluir "el paciente se realiza..." en datos clínicos.
- Órganos no mencionados por el dictado se asumen y redactan como normales.
- Cada idea en línea independiente.

REGLAS DURAS (umbrales — no contradecir las cifras):
- Esteatosis hepática solo si hígado <40 UH o hígado ≤ bazo-10 UH. Si hígado > bazo, NO hay esteatosis.
- Lipoma solo con densidad grasa (-120 a -30 UH). ~3 UH es líquido, no lipoma.
- Páncreas lipomatoso: 40-60 UH es normal; no diagnosticar lipomatosis en ese rango.
- Realce verdadero: diferencia ≥10 UH entre fases. <10 UH = sin realce.
- Aorta abdominal: normal <30 mm, ectasia 25-29 mm, aneurisma ≥30 mm.

REGLAS BLANDAS (criterio):
- No mencionar "sin signos de pancreatitis aguda" salvo clínica/sospecha aguda.
- Suprarrenal 10-15 UH en estudio CON contraste: no cerrar adenoma; sugerir TC sin contraste o RM.
- Septos quísticos renales ~3 mm: no es Bosniak II; clasificar Bosniak IIF.
- No usar O-RADS en TC; describir la lesión y recomendar caracterización (eco TV/RM).
- Valorar SIEMPRE hígado (esteatosis por UH) y, según clínica, ampliar la estructura relevante.
- En litiasis: consignar densidad UH del cálculo (orienta manejo urológico).
- Graduar obstrucción urinaria con terminología precisa (hidronefrosis/ureteropielocaliectasia grado).
- Nódulo pulmonar en contexto de neoplasia: potencialmente metastásico hasta demostrar lo contrario.
- Hallazgos no relacionados anatómicamente se redactan como eventos independientes.
- Si la clínica no se explica por los hallazgos: "Sin hallazgos estructurales que justifiquen la clínica referida".

No inventes datos. No uses edad/sexo/hospital en el informe. Lenguaje médico sobrio y directo."""


class FabricaAbdomenCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir, self.mod = load_app_copy()
        self.client = self.mod.app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def read_dataset_rows(self):
        if not self.mod.DATASET.exists():
            return []
        return [
            json.loads(line)
            for line in self.mod.DATASET.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def json_files(self):
        return sorted(self.mod.CASOS_DIR.glob("caso_*.json"))

    def md_files(self):
        return sorted(self.mod.CASOS_DIR.glob("caso_*.md"))

    def test_optimus_app_es_entrypoint_principal_y_wrapper_no_duplica_logica(self):
        wrapper = WRAPPER_SOURCE.read_text(encoding="utf-8")
        principal = APP_SOURCE.read_text(encoding="utf-8")

        self.assertEqual(APP_SOURCE.name, "optimus_app.py")
        self.assertIn("from optimus_app import app", wrapper)
        self.assertIn("Punto de entrada recomendado: python 00_APP/optimus_app.py", wrapper)
        self.assertNotIn("PAGINA = r", wrapper)
        self.assertNotIn("def route_guardar", wrapper)
        self.assertIn("PAGINA = r", principal)

    def test_prompt_se_carga_desde_archivo_externo_y_es_identico_al_anterior(self):
        prompt_path = self.mod.REGION_CONFIG.PROMPT_PATH

        self.assertEqual(prompt_path.name, "SYSTEM_PROMPT_abdomen.txt")
        self.assertEqual(self.mod.SYSTEM_PROMPT, prompt_path.read_text(encoding="utf-8").rstrip("\n"))
        self.assertEqual(self.mod.SYSTEM_PROMPT, LEGACY_PROMPT_ABDOMEN)
        self.assertNotIn("SYSTEM_PROMPT = \"\"\"", APP_SOURCE.read_text(encoding="utf-8"))

    def test_error_claro_si_falta_prompt(self):
        missing = Path(self.tmpdir.name) / "01_abdomen" / "NO_EXISTE.txt"

        with self.assertRaises(SystemExit) as ctx:
            self.mod._cargar_system_prompt(missing)

        self.assertIn("No se encontró el SYSTEM_PROMPT de abdomen", str(ctx.exception))

    def test_error_claro_si_prompt_esta_vacio(self):
        empty = Path(self.tmpdir.name) / "empty_prompt.txt"
        empty.write_text("  \n", encoding="utf-8")

        with self.assertRaises(SystemExit) as ctx:
            self.mod._cargar_system_prompt(empty)

        self.assertIn("está vacío", str(ctx.exception))

    def test_app_usa_validador_regional_y_no_logica_compacta_activa(self):
        source = APP_SOURCE.read_text(encoding="utf-8")

        self.assertEqual(
            Path(self.mod.VALIDADOR_REGIONAL.__file__).name,
            "validador_abdomen.py",
        )
        self.assertNotIn("def _uh_organo", source)
        self.assertNotIn("NUM_PAL =", source)
        self.assertNotIn("_RE_UH =", source)

    def test_error_claro_si_falla_carga_del_validador(self):
        missing = Path(self.tmpdir.name) / "01_abdomen" / "NO_EXISTE_VALIDATOR.py"

        with self.assertRaises(SystemExit) as ctx:
            self.mod._cargar_validador_regional(missing)

        self.assertIn("No se encontró el validador regional de abdomen", str(ctx.exception))

    def test_reglas_regionales_d2_d6_d7_y_d11_estan_activas(self):
        textos = {
            "D2": "Datos clínicos: control.\nHallazgos: estenosis del cincuenta por ciento.\nImpresión diagnóstica: estenosis.",
            "D6": "Datos clínicos: control.\nHallazgos: varios.\nImpresión diagnóstica: Primera conclusión. Segunda conclusión. Tercera conclusión. Cuarta conclusión con texto adicional largo para superar claramente el umbral heurístico del validador regional y documentar el comportamiento activo.",
            "D7": "Datos clínicos: control.\nFONASA: prueba.\nHallazgos: sin hallazgos.\nImpresión diagnóstica: sin hallazgos.",
            "D11": "Datos clínicos: control.\nHallazgos: Lesión que realza. Fase simple 40 UH. Fase portal 45 UH.\nImpresión diagnóstica: lesión que realza.",
        }
        for regla, texto in textos.items():
            with self.subTest(regla=regla):
                reglas = {flag["regla"] for flag in self.mod.validar(texto)}
                self.assertIn(regla, reglas)

    def test_generar_informe_con_caso_bruto_y_validador(self):
        informe = (
            "Datos clinicos: control\n"
            "Hallazgos: Hígado de 55 UH y bazo de 50 UH. Esteatosis hepática.\n"
            "Impresión diagnóstica: Esteatosis hepática.\n"
            "Interpretación global: prueba."
        )
        with patch.object(self.mod, "generar_informe", return_value=informe) as mocked:
            response = self.client.post(
                "/generar",
                json={
                    "caso": "dolor abdominal. higado 55 uh bazo 50 uh",
                    "key": "test-key",
                    "provider": "openai",
                    "model": "modelo-falso",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["informe"], informe)
        self.assertEqual(data["provider"], "openai")
        self.assertEqual(data["model"], "modelo-falso")
        self.assertTrue(any(flag["regla"] == "D8" for flag in data["flags"]))
        mocked.assert_called_once()

    def test_generar_informe_openai_usa_mock_sin_llamada_externa(self):
        fake_client = MagicMock()
        with patch("openai.OpenAI", return_value=fake_client) as openai_cls, patch.object(
            self.mod, "_openai_compat_chat", return_value="informe openai"
        ) as compat:
            result = self.mod.generar_informe(
                "caso bruto", "test-key", modelo="gpt-test", proveedor="openai"
            )

        self.assertEqual(result, "informe openai")
        openai_cls.assert_called_once_with(api_key="test-key")
        compat.assert_called_once_with(
            fake_client, "gpt-test", self.mod.SYSTEM_PROMPT, "caso bruto"
        )

    def test_generar_informe_deepseek_usa_mock_sin_llamada_externa(self):
        fake_client = MagicMock()
        with patch("openai.OpenAI", return_value=fake_client) as openai_cls, patch.object(
            self.mod, "_openai_compat_chat", return_value="informe deepseek"
        ) as compat:
            result = self.mod.generar_informe(
                "caso bruto", "deepseek-key", modelo="deepseek-chat", proveedor="deepseek"
            )

        self.assertEqual(result, "informe deepseek")
        openai_cls.assert_called_once_with(
            api_key="deepseek-key", base_url="https://api.deepseek.com"
        )
        compat.assert_called_once_with(
            fake_client, "deepseek-chat", self.mod.SYSTEM_PROMPT, "caso bruto"
        )

    def test_openai_uses_responses_api_when_chat_completion_has_no_text(self):
        fake_client = MagicMock()
        chat_response = MagicMock()
        chat_response.choices = [MagicMock()]
        chat_response.choices[0].message.content = None
        fake_client.chat.completions.create.return_value = chat_response
        fake_client.responses.create.return_value.output_text = "Informe recuperado por Responses API."

        result = self.mod._openai_compat_chat(
            fake_client, "gpt-5.6-luna", "instrucciones", "caso de prueba"
        )

        self.assertEqual(result, "Informe recuperado por Responses API.")
        fake_client.responses.create.assert_called_once_with(
            model="gpt-5.6-luna",
            instructions="instrucciones",
            input="caso de prueba",
            temperature=0.2,
        )

    def test_generar_rechaza_un_informe_vacio_antes_de_mostrarlo(self):
        with patch.object(self.mod, "generar_informe", return_value=""):
            response = self.client.post(
                "/generar",
                json={
                    "caso": "dolor abdominal",
                    "key": "test-key",
                    "provider": "openai",
                    "model": "modelo-falso",
                },
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn("ningún informe vacío", response.get_json()["error"])

    def test_generar_informe_anthropic_usa_mock_sin_llamada_externa(self):
        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_client.messages.create.return_value = fake_response
        with patch("anthropic.Anthropic", return_value=fake_client) as anthropic_cls, patch.object(
            self.mod, "_texto_anthropic", return_value="informe anthropic"
        ) as texto:
            result = self.mod.generar_informe(
                "caso bruto", "anthropic-key", modelo="claude-test", proveedor="anthropic"
            )

        self.assertEqual(result, "informe anthropic")
        anthropic_cls.assert_called_once_with(api_key="anthropic-key")
        fake_client.messages.create.assert_called_once()
        texto.assert_called_once_with(fake_response)

    def test_frontend_conserva_input_original_para_guardar(self):
        pagina = self.mod.PAGINA

        self.assertIn("currentCaseInput", pagina)
        self.assertIn("currentCaseInput=caso", pagina)
        self.assertIn("caso:currentCaseInput", pagina)
        self.assertIn("$('caso').value=''", pagina)

    def test_guardar_persiste_input_original_y_esquema_v1(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dictado bruto conservado",
                "informe_ia": "Informe IA original",
                "informe_final": "Informe final corregido",
                "correccion": "Cambio terminológico explicado",
                "provider": "anthropic",
                "model": "claude-test",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        case_id = data["archivo"].replace("caso_", "")

        md_path = self.mod.CASOS_DIR / f"caso_{case_id}.md"
        json_path = self.mod.CASOS_DIR / f"caso_{case_id}.json"
        self.assertTrue(md_path.exists())
        self.assertTrue(json_path.exists())

        md_text = md_path.read_text(encoding="utf-8")
        record = json.loads(json_path.read_text(encoding="utf-8"))
        rows = self.read_dataset_rows()

        required = {
            "case_id",
            "timestamp",
            "dataset_schema_version",
            "region",
            "origen",
            "modalidad",
            "input",
            "informe_ia",
            "correccion_radiologo",
            "informe_final",
            "explicacion",
            "proveedor",
            "modelo",
            "prompt_version",
            "validator_version",
            "validacion_humana",
            "fecha_validacion",
            "validated_by",
            "tiene_correccion",
            "case_status",
            "gold_standard",
            "flags",
        }
        self.assertTrue(required.issubset(record.keys()))
        self.assertTrue(required.issubset(rows[-1].keys()))
        self.assertEqual(record.keys(), rows[-1].keys())

        self.assertIn("dictado bruto conservado", md_text)
        self.assertEqual(record["input"], "dictado bruto conservado")
        self.assertEqual(record["informe_ia"], "Informe IA original")
        self.assertEqual(record["informe_final"], "Informe final corregido")
        self.assertEqual(record["correccion_radiologo"], "Cambio terminológico explicado")
        self.assertEqual(record["region"], "abdomen")
        self.assertEqual(record["origen"], "app_local")
        self.assertEqual(record["proveedor"], "anthropic")
        self.assertEqual(record["modelo"], "claude-test")
        self.assertEqual(record["prompt_version"], "abdomen-1.0")
        self.assertEqual(record["validator_version"], "abdomen-1.0")
        self.assertEqual(record["dataset_schema_version"], "1.0")
        self.assertFalse(record["validacion_humana"])
        self.assertFalse(record["gold_standard"])
        self.assertTrue(record["tiene_correccion"])
        self.assertEqual(record["case_status"], "corrected")
        self.assertTrue(all("bloquea_gold" in flag for flag in record["flags"]))

    def test_validacion_humana_explicita_y_gold_standard_true(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dictado bruto validado",
                "informe_ia": "Informe final limpio",
                "informe_final": "Informe final limpio",
                "correccion": "",
                "provider": "openai",
                "model": "gpt-test",
                "validacion_humana": True,
                "fecha_validacion": "2026-07-18T22:45:00.000Z",
                "validated_by": "radiologo",
                "case_status": "validated",
            },
        )

        self.assertEqual(response.status_code, 200)
        case_id = response.get_json()["archivo"].replace("caso_", "")
        record = json.loads(
            (self.mod.CASOS_DIR / f"caso_{case_id}.json").read_text(encoding="utf-8")
        )

        self.assertTrue(record["validacion_humana"])
        self.assertEqual(record["fecha_validacion"], "2026-07-18T22:45:00.000Z")
        self.assertEqual(record["validated_by"], "radiologo")
        self.assertEqual(record["case_status"], "validated")
        self.assertTrue(record["gold_standard"])

    def test_validacion_humana_por_defecto_false_y_no_gold(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dictado bruto no validado",
                "informe_ia": "Informe limpio",
                "informe_final": "Informe limpio",
                "correccion": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        case_id = response.get_json()["archivo"].replace("caso_", "")
        record = json.loads(
            (self.mod.CASOS_DIR / f"caso_{case_id}.json").read_text(encoding="utf-8")
        )
        self.assertFalse(record["validacion_humana"])
        self.assertFalse(record["gold_standard"])

    def test_editar_despues_de_validar_invalida_en_frontend(self):
        pagina = self.mod.PAGINA

        self.assertIn("function marcarNoValidado()", pagina)
        self.assertIn("function validarGold()", pagina)
        self.assertIn("marcarNoValidado()", pagina)
        self.assertIn("addEventListener('input'", pagina)

    def test_gold_standard_false_con_bloqueo_critico(self):
        registro = {
            "validacion_humana": True,
            "case_status": "validated",
            "input": "input",
            "informe_final": "informe",
            "dataset_schema_version": "1.0",
            "flags": [{"regla": "D8", "gravedad": "alta", "mensaje": "bloqueo", "bloquea_gold": True}],
        }

        self.assertFalse(self.mod._calcular_gold_standard(registro))

    def test_gold_standard_requiere_estado_validated_y_no_bloquea_por_estilo(self):
        registro = {
            "validacion_humana": True,
            "case_status": "corrected",
            "input": "input",
            "informe_final": "informe",
            "dataset_schema_version": "1.0",
            "flags": [],
        }
        self.assertFalse(self.mod._calcular_gold_standard(registro))

        registro["case_status"] = "validated"
        registro["flags"] = [{"regla": "D11", "gravedad": "media", "mensaje": "aviso de estilo"}]
        self.assertTrue(self.mod._calcular_gold_standard(registro))

    def test_guardar_rechaza_input_vacio_y_no_crea_archivos(self):
        before_json = self.json_files()
        before_md = self.md_files()
        before_dataset = self.mod.DATASET.exists()

        response = self.client.post(
            "/guardar",
            json={
                "caso": "   ",
                "informe_ia": "Informe IA",
                "informe_final": "Informe final",
                "correccion": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("caso bruto", response.get_json()["error"])
        self.assertEqual(before_json, self.json_files())
        self.assertEqual(before_md, self.md_files())
        self.assertEqual(before_dataset, self.mod.DATASET.exists())

    def test_importacion_hospital_casa_usa_misma_persistencia(self):
        texto = """### CASO ###
[REGION]: abdomen
[BRUTO]:
dolor abdominal importado
[INFORME]:
Datos clínicos: dolor abdominal.
Hallazgos: sin hallazgos relevantes.
Impresión diagnóstica: sin hallazgos agudos.
[MEJORAS]:
ajuste de estilo
[NOTAS]:
caso de prueba
### FIN ###"""
        response = self.client.post("/importar", json={"texto": texto})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["importados"], 1)
        case_id = data["resultados"][0]["case_id"]
        record = json.loads(
            (self.mod.CASOS_DIR / f"caso_{case_id}.json").read_text(encoding="utf-8")
        )
        rows = self.read_dataset_rows()

        self.assertEqual(record.keys(), rows[-1].keys())
        self.assertEqual(record["region"], "abdomen")
        self.assertEqual(record["origen"], "importador_hospital")
        self.assertEqual(record["case_status"], "imported_pending")
        self.assertEqual(rows[-1]["region"], "abdomen")
        self.assertEqual(rows[-1]["origen"], "importador_hospital")
        self.assertIn("Mejoras: ajuste de estilo", record["correccion_radiologo"])
        self.assertIn("Notas: caso de prueba", record["correccion_radiologo"])

    def test_configuracion_y_actualizacion_del_prompt_con_diff(self):
        nuevo_prompt = self.mod.SYSTEM_PROMPT + "\n- Regla administrativa de prueba"
        raw = json.dumps(
            {
                "respuesta": "Propuesta preparada",
                "nuevo_system_prompt": nuevo_prompt,
                "resumen_cambio": "Añade una regla de prueba",
            },
            ensure_ascii=False,
        )
        with patch.object(self.mod, "_llm_chat_text", return_value=raw):
            proposal = self.client.post(
                "/admin_chat",
                json={
                    "mensaje": "añade una regla de prueba",
                    "key": "test-key",
                    "provider": "openai",
                    "model": "modelo-falso",
                },
            )

        self.assertEqual(proposal.status_code, 200)
        proposal_data = proposal.get_json()
        self.assertEqual(proposal_data["tipo"], "prompt")
        self.assertIn("Regla administrativa de prueba", proposal_data["diff"])

        applied = self.client.post("/aplicar_prompt")
        applied_data = applied.get_json()
        self.assertTrue(applied_data["ok"])
        self.assertEqual(applied_data["prompt_version"], "abdomen-1.0+override.1")
        self.assertIn("Regla administrativa de prueba", self.mod.SYSTEM_PROMPT)
        self.assertTrue(self.mod.CONFIG_PATH.exists())
        self.assertTrue(any(self.mod.HISTORIAL_DIR.glob("prompt_abdomen-1_0_*.txt")))

        config = self.client.get("/config").get_json()
        self.assertIn("prompt_base", config)
        self.assertIn("prompt_override", config)
        self.assertIn("prompt_efectivo", config)
        self.assertEqual(config["prompt_version"], "abdomen-1.0+override.1")
        self.assertEqual(config["prompt_base"], self.mod.PROMPT_BASE)
        self.assertIn("Regla administrativa de prueba", config["prompt_override"])
        self.assertIn("Regla administrativa de prueba", config["prompt_efectivo"])
        self.assertEqual(self.mod.APP_CONFIG["prompt_events"][-1]["usuario"], "radiologo")

        restored = self.client.post("/restaurar_prompt_base").get_json()
        self.assertTrue(restored["ok"])
        self.assertEqual(restored["prompt_version"], "abdomen-1.0")
        self.assertEqual(self.mod.SYSTEM_PROMPT, self.mod.PROMPT_BASE)

    def test_guardar_prompt_borrador_no_cambia_prompt_efectivo(self):
        nuevo_prompt = self.mod.PROMPT_BASE + "\n- Borrador de prueba"
        response = self.client.post(
            "/guardar_prompt_borrador",
            json={"prompt": nuevo_prompt, "motivo": "prueba de borrador"},
        )

        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["prompt_version"], "abdomen-1.0")
        self.assertEqual(self.mod.SYSTEM_PROMPT, self.mod.PROMPT_BASE)
        self.assertIn("Borrador de prueba", self.mod.APP_CONFIG["prompt_draft"])
        self.assertEqual(self.mod.APP_CONFIG["prompt_events"][-1]["accion"], "guardar_borrador")

    def test_reglas_candidatas_crear_listar_aceptar_y_descartar(self):
        propuesta = {
            "tipo": "regla",
            "categoria": "terminologia",
            "regla": "No usar término de prueba.",
            "motivo": "Aparece como corrección repetible.",
        }
        with patch.object(
            self.mod, "proponer_regla_desde_correccion", return_value=propuesta
        ):
            saved = self.client.post(
                "/guardar",
                json={
                    "caso": "caso con corrección",
                    "informe_ia": "texto inicial",
                    "informe_final": "texto final",
                    "correccion": "sustituí un término",
                    "key": "test-key",
                    "provider": "openai",
                    "model": "modelo-falso",
                },
            )

        self.assertEqual(saved.status_code, 200)
        candidata = saved.get_json()["candidata"]
        self.assertEqual(candidata["estado"], "pendiente")

        listed = self.client.get("/candidatas").get_json()
        self.assertEqual(listed["total"], 1)

        accepted = self.client.post(
            "/candidata_aceptar", json={"ts": candidata["ts"]}
        ).get_json()
        self.assertTrue(accepted["ok"])
        self.assertIn("No usar término de prueba.", accepted["diff"])
        self.assertIn("No usar término de prueba.", self.mod.ULTIMA_PROPUESTA["prompt"])

        self.mod.REGLAS_CANDIDATAS.write_text(
            json.dumps(
                {
                    "ts": "pendiente-descartar",
                    "tipo": "puntual",
                    "categoria": "otro",
                    "regla": "",
                    "motivo": "No generalizable",
                    "estado": "pendiente",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        discarded = self.client.post(
            "/candidata_descartar", json={"ts": "pendiente-descartar"}
        ).get_json()
        self.assertTrue(discarded["ok"])

    def test_tags_dataset_entry_generan_aviso_y_bloquean_guardado(self):
        informe_con_marcadores = (
            "Datos clínicos: prueba.\n"
            "Hallazgos: sin hallazgos.\n"
            "Impresión diagnóstica: sin hallazgos agudos.\n"
            "TAGS: abdomen, prueba\n"
            "DATASET_ENTRY: {'x': 1}"
        )
        with patch.object(
            self.mod, "generar_informe", return_value=informe_con_marcadores
        ):
            generated = self.client.post(
                "/generar",
                json={
                    "caso": "caso bruto",
                    "key": "test-key",
                    "provider": "openai",
                    "model": "modelo-falso",
                },
            ).get_json()

        self.assertTrue(any(flag["regla"] == "META_VISIBLE" for flag in generated["flags"]))
        self.assertTrue(
            any(flag["regla"] == "META_VISIBLE" and flag["bloquea_gold"] for flag in generated["flags"])
        )

        before_json = self.json_files()
        before_md = self.md_files()
        response = self.client.post(
            "/guardar",
            json={
                "caso": "caso bruto",
                "informe_ia": generated["informe"],
                "informe_final": generated["informe"],
                "correccion": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            any(flag["regla"] == "META_VISIBLE" for flag in response.get_json()["flags"])
        )
        self.assertEqual(before_json, self.json_files())
        self.assertEqual(before_md, self.md_files())

    def test_registros_historicos_sin_campos_nuevos_se_leen_sin_error(self):
        old_id = "19990101_010101"
        old_record = {
            "input": "input historico",
            "informe_ia": "ia historico",
            "informe_final": "final historico",
            "correccion": "correccion antigua",
            "hubo_correccion": True,
            "ts": old_id,
            "flags": [],
        }
        (self.mod.CASOS_DIR / f"caso_{old_id}.json").write_text(
            json.dumps(old_record, ensure_ascii=False), encoding="utf-8"
        )

        response = self.client.get(f"/caso/{old_id}")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["case_id"], old_id)
        self.assertEqual(data["correccion_radiologo"], "correccion antigua")
        self.assertTrue(data["tiene_correccion"])
        self.assertEqual(data["region"], "abdomen")
        self.assertIn("dataset_schema_version", data)

    def test_registro_regional_habilita_cinco_regiones_y_carga_componentes(self):
        self.assertEqual(self.mod.current_region, "abdomen")
        self.assertEqual(self.mod.REGION_CONFIG.REGION_ID, "abdomen")
        regiones = self.mod.list_regions()
        self.assertEqual(
            regiones,
            [
                {"region_id": "abdomen", "enabled": True},
                {"region_id": "lumbar", "enabled": True},
                {"region_id": "cervical", "enabled": True},
                {"region_id": "rodilla", "enabled": True},
                {"region_id": "mano_muneca", "enabled": True},
                {"region_id": "codo", "enabled": True},
                {"region_id": "tobillo_pie", "enabled": True},
                {"region_id": "torax", "enabled": True},
            ],
        )
        respuesta_registro = self.client.get("/regiones").get_json()
        self.assertEqual(respuesta_registro["current_region"], "abdomen")
        self.assertEqual(
            [region["region_id"] for region in respuesta_registro["regions"]],
            ["abdomen", "lumbar", "cervical", "rodilla", "mano_muneca", "codo", "tobillo_pie", "torax"],
        )
        self.assertTrue(all(region["enabled"] for region in respuesta_registro["regions"]))
        self.assertIn("Mano y muñeca", [region["region_name"] for region in respuesta_registro["regions"]])
        self.assertIn("Codo", [region["region_name"] for region in respuesta_registro["regions"]])
        self.assertIn("Tobillo y pie", [region["region_name"] for region in respuesta_registro["regions"]])
        self.assertIn("Tórax", [region["region_name"] for region in respuesta_registro["regions"]])

        prompt = self.mod.load_region_prompt("abdomen")
        validador = self.mod.load_region_validator("abdomen")
        self.assertEqual(prompt, self.mod.PROMPT_BASE)
        self.assertTrue(hasattr(validador, "validar"))
        self.assertEqual(self.mod.CASOS_DIR, self.mod.REGION_CONFIG.CASES_DIR)
        self.assertEqual(self.mod.DATASET, self.mod.REGION_CONFIG.DATASET_PATH)

        lumbar_prompt = self.mod.load_region_prompt("lumbar")
        lumbar_validador = self.mod.load_region_validator("lumbar")
        self.assertIn("columna lumbar", lumbar_prompt.lower())
        self.assertTrue(hasattr(lumbar_validador, "validar"))

        cervical_prompt = self.mod.load_region_prompt("cervical")
        cervical_validador = self.mod.load_region_validator("cervical")
        self.assertIn("columna cervical", cervical_prompt.lower())
        self.assertTrue(hasattr(cervical_validador, "validar"))

        rodilla_prompt = self.mod.load_region_prompt("rodilla")
        rodilla_validador = self.mod.load_region_validator("rodilla")
        self.assertIn("rm de rodilla", rodilla_prompt.lower())
        self.assertTrue(hasattr(rodilla_validador, "validar"))

        mano_prompt = self.mod.load_region_prompt("mano_muneca")
        mano_validador = self.mod.load_region_validator("mano_muneca")
        self.assertIn("mano y muñeca", mano_prompt.lower())
        self.assertTrue(hasattr(mano_validador, "validar"))

    def test_selector_visible_muestra_cinco_regiones_y_confirma_cambio(self):
        pagina = self.mod.PAGINA

        self.assertIn('<select id="region"', pagina)
        self.assertIn('<option value="abdomen">Abdomen</option>', pagina)
        self.assertIn('<option value="lumbar">Columna lumbar</option>', pagina)
        self.assertIn('<option value="cervical">Columna cervical</option>', pagina)
        self.assertIn('<option value="rodilla">Rodilla</option>', pagina)
        self.assertIn("mano_muneca:'Mano y muñeca'", pagina)
        self.assertIn("codo:'Codo'", pagina)
        self.assertIn("tobillo_pie:'Tobillo y pie'", pagina)
        self.assertIn("torax:'Tórax'", pagina)
        self.assertIn("renderThoraxControls", pagina)
        self.assertIn("function regionChanged()", pagina)
        self.assertIn("confirm('Cambiar de región", pagina)
        self.assertIn("currentRegion=\"abdomen\"", pagina)

    def test_cambio_a_lumbar_carga_prompt_validador_rutas_y_versiones(self):
        response = self.client.post("/region", json={"region": "lumbar"})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(self.mod.current_region, "lumbar")
        self.assertEqual(self.mod.REGION_CONFIG.REGION_ID, "lumbar")
        self.assertEqual(self.mod.REGION_NAME, "Columna lumbar")
        self.assertEqual(self.mod.PROMPT_VERSION, "lumbar-1.0")
        self.assertEqual(self.mod.VALIDATOR_VERSION, "lumbar-1.0")
        self.assertIn("columna lumbar", self.mod.SYSTEM_PROMPT.lower())
        self.assertEqual(self.mod.CASOS_DIR, self.mod.REGION_CONFIG.CASES_DIR)
        self.assertEqual(self.mod.DATASET, self.mod.REGION_CONFIG.DATASET_PATH)
        self.assertIn("casos_lumbar", str(self.mod.CASOS_DIR))
        self.assertIn("lumbar_dataset.jsonl", str(self.mod.DATASET))

    def test_cambio_a_cervical_carga_prompt_validador_rutas_y_versiones(self):
        response = self.client.post("/region", json={"region": "cervical"})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(self.mod.current_region, "cervical")
        self.assertEqual(self.mod.REGION_CONFIG.REGION_ID, "cervical")
        self.assertEqual(self.mod.REGION_NAME, "Columna cervical")
        self.assertEqual(self.mod.PROMPT_VERSION, "cervical-1.0")
        self.assertEqual(self.mod.VALIDATOR_VERSION, "cervical-1.0")
        self.assertIn("columna cervical", self.mod.SYSTEM_PROMPT.lower())
        self.assertIn("casos_cervical", str(self.mod.CASOS_DIR))
        self.assertIn("cervical_dataset.jsonl", str(self.mod.DATASET))

    def test_cambio_a_rodilla_carga_prompt_validador_rutas_y_versiones(self):
        response = self.client.post("/region", json={"region": "rodilla"})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(self.mod.current_region, "rodilla")
        self.assertEqual(self.mod.REGION_CONFIG.REGION_ID, "rodilla")
        self.assertEqual(self.mod.REGION_NAME, "Rodilla")
        self.assertEqual(self.mod.PROMPT_VERSION, "rodilla-1.0")
        self.assertEqual(self.mod.VALIDATOR_VERSION, "rodilla-1.0")
        self.assertIn("rm de rodilla", self.mod.SYSTEM_PROMPT.lower())
        self.assertIn("casos_rodilla", str(self.mod.CASOS_DIR))
        self.assertIn("rodilla_dataset.jsonl", str(self.mod.DATASET))

    def test_overrides_historiales_y_candidatas_son_independientes_por_region(self):
        abdomen_prompt = self.mod.PROMPT_BASE + "\n- Override abdomen prueba"
        self.client.post("/guardar_prompt_borrador", json={"prompt": abdomen_prompt})
        abdomen_applied = self.client.post("/aplicar_prompt").get_json()
        abdomen_config_path = self.mod.CONFIG_PATH
        abdomen_history = self.mod.HISTORIAL_DIR
        abdomen_candidates = self.mod.REGLAS_CANDIDATAS
        self.assertEqual(abdomen_applied["prompt_version"], "abdomen-1.0+override.1")

        self.client.post("/region", json={"region": "lumbar"})
        self.assertNotEqual(self.mod.CONFIG_PATH, abdomen_config_path)
        self.assertNotEqual(self.mod.HISTORIAL_DIR, abdomen_history)
        self.assertNotEqual(self.mod.REGLAS_CANDIDATAS, abdomen_candidates)
        self.assertNotIn("Override abdomen prueba", self.mod.SYSTEM_PROMPT)

        lumbar_prompt = self.mod.PROMPT_BASE + "\n- Override lumbar prueba"
        self.client.post("/guardar_prompt_borrador", json={"prompt": lumbar_prompt})
        lumbar_applied = self.client.post("/aplicar_prompt").get_json()
        self.assertEqual(lumbar_applied["prompt_version"], "lumbar-1.0+override.1")
        self.assertIn("Override lumbar prueba", self.mod.SYSTEM_PROMPT)

        self.client.post("/region", json={"region": "abdomen"})
        self.assertIn("Override abdomen prueba", self.mod.SYSTEM_PROMPT)
        self.assertNotIn("Override lumbar prueba", self.mod.SYSTEM_PROMPT)

    def test_override_historial_y_candidatas_cervical_independientes(self):
        self.client.post("/region", json={"region": "cervical"})
        cervical_config_path = self.mod.CONFIG_PATH
        cervical_history = self.mod.HISTORIAL_DIR
        cervical_candidates = self.mod.REGLAS_CANDIDATAS
        cervical_prompt = self.mod.PROMPT_BASE + "\n- Override cervical prueba"

        self.client.post("/guardar_prompt_borrador", json={"prompt": cervical_prompt})
        applied = self.client.post("/aplicar_prompt").get_json()

        self.assertEqual(applied["prompt_version"], "cervical-1.0+override.1")
        self.assertIn("Override cervical prueba", self.mod.SYSTEM_PROMPT)
        self.assertIn("03_cervical", str(cervical_config_path))
        self.assertIn("03_cervical", str(cervical_history))
        self.assertIn("03_cervical", str(cervical_candidates))

        self.client.post("/region", json={"region": "abdomen"})
        self.assertNotIn("Override cervical prueba", self.mod.SYSTEM_PROMPT)
        self.client.post("/region", json={"region": "lumbar"})
        self.assertNotIn("Override cervical prueba", self.mod.SYSTEM_PROMPT)

    def test_override_historial_y_candidatas_rodilla_independientes(self):
        self.client.post("/region", json={"region": "rodilla"})
        rodilla_config_path = self.mod.CONFIG_PATH
        rodilla_history = self.mod.HISTORIAL_DIR
        rodilla_candidates = self.mod.REGLAS_CANDIDATAS
        rodilla_prompt = self.mod.PROMPT_BASE + "\n- Override rodilla prueba"

        self.client.post("/guardar_prompt_borrador", json={"prompt": rodilla_prompt})
        applied = self.client.post("/aplicar_prompt").get_json()

        self.assertEqual(applied["prompt_version"], "rodilla-1.0+override.1")
        self.assertIn("Override rodilla prueba", self.mod.SYSTEM_PROMPT)
        self.assertIn("05_rodilla", str(rodilla_config_path))
        self.assertIn("05_rodilla", str(rodilla_history))
        self.assertIn("05_rodilla", str(rodilla_candidates))

        for region in ["abdomen", "lumbar", "cervical"]:
            self.client.post("/region", json={"region": region})
            self.assertNotIn("Override rodilla prueba", self.mod.SYSTEM_PROMPT)

    def test_caso_lumbar_se_guarda_solo_en_dataset_lumbar(self):
        self.client.post("/region", json={"region": "lumbar"})
        lumbar_dataset = self.mod.DATASET
        abdomen_dataset = self.mod.get_region_config("abdomen").DATASET_PATH

        response = self.client.post(
            "/guardar",
            json={
                "caso": "dolor lumbar con protrusion L4-L5",
                "informe_ia": "Datos clínicos: dolor lumbar.\nHallazgos: sin estenosis.\nImpresión diagnóstica: sin hallazgos agudos.",
                "informe_final": "Datos clínicos: dolor lumbar.\nHallazgos: sin estenosis.\nImpresión diagnóstica: sin hallazgos agudos.",
                "correccion": "",
                "case_status": "generated",
            },
        )

        self.assertEqual(response.status_code, 200)
        rows_lumbar = [
            json.loads(line)
            for line in lumbar_dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(rows_lumbar[-1]["region"], "lumbar")
        self.assertEqual(rows_lumbar[-1]["region_name"], "Columna lumbar")
        self.assertEqual(rows_lumbar[-1]["prompt_version"], "lumbar-1.0")
        self.assertEqual(rows_lumbar[-1]["validator_version"], "lumbar-1.0")
        if abdomen_dataset.exists():
            self.assertNotIn("dolor lumbar con protrusion L4-L5", abdomen_dataset.read_text(encoding="utf-8"))

    def test_caso_abdomen_no_aparece_en_dataset_lumbar(self):
        lumbar_dataset = self.mod.get_region_config("lumbar").DATASET_PATH
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dolor abdominal aislado",
                "informe_ia": "Informe abdomen",
                "informe_final": "Informe abdomen",
                "correccion": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        if lumbar_dataset.exists():
            self.assertNotIn("dolor abdominal aislado", lumbar_dataset.read_text(encoding="utf-8"))

    def test_caso_cervical_se_guarda_solo_en_dataset_cervical(self):
        self.client.post("/region", json={"region": "cervical"})
        cervical_dataset = self.mod.DATASET
        abdomen_dataset = self.mod.get_region_config("abdomen").DATASET_PATH
        lumbar_dataset = self.mod.get_region_config("lumbar").DATASET_PATH

        response = self.client.post(
            "/guardar",
            json={
                "caso": "cervicalgia con protrusion C5-C6",
                "informe_ia": "Datos clínicos: cervicalgia.\nExploración: RM columna cervical.\nHallazgos: protrusión paracentral C5-C6.\nImpresión diagnóstica: protrusión paracentral C5-C6.",
                "informe_final": "Datos clínicos: cervicalgia.\nExploración: RM columna cervical.\nHallazgos: protrusión paracentral C5-C6.\nImpresión diagnóstica: protrusión paracentral C5-C6.",
                "correccion": "",
                "case_status": "generated",
            },
        )

        self.assertEqual(response.status_code, 200)
        rows_cervical = [
            json.loads(line)
            for line in cervical_dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(rows_cervical[-1]["region"], "cervical")
        self.assertEqual(rows_cervical[-1]["region_name"], "Columna cervical")
        self.assertEqual(rows_cervical[-1]["prompt_version"], "cervical-1.0")
        self.assertEqual(rows_cervical[-1]["validator_version"], "cervical-1.0")
        if abdomen_dataset.exists():
            self.assertNotIn("cervicalgia con protrusion C5-C6", abdomen_dataset.read_text(encoding="utf-8"))
        if lumbar_dataset.exists():
            self.assertNotIn("cervicalgia con protrusion C5-C6", lumbar_dataset.read_text(encoding="utf-8"))

    def test_caso_rodilla_se_guarda_solo_en_dataset_rodilla(self):
        self.client.post("/region", json={"region": "rodilla"})
        rodilla_dataset = self.mod.DATASET
        otras = [
            self.mod.get_region_config("abdomen").DATASET_PATH,
            self.mod.get_region_config("lumbar").DATASET_PATH,
            self.mod.get_region_config("cervical").DATASET_PATH,
        ]

        response = self.client.post(
            "/guardar",
            json={
                "caso": "dolor de rodilla con condropatia patelar",
                "informe_ia": "Datos clínicos: dolor.\nExploración: RM rodilla derecha.\nHallazgos: condropatía grado II.\nImpresión diagnóstica: condropatía grado II.",
                "informe_final": "Datos clínicos: dolor.\nExploración: RM rodilla derecha.\nHallazgos: condropatía grado II.\nImpresión diagnóstica: condropatía grado II.",
                "correccion": "",
                "case_status": "generated",
            },
        )

        self.assertEqual(response.status_code, 200)
        rows_rodilla = [
            json.loads(line)
            for line in rodilla_dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(rows_rodilla[-1]["region"], "rodilla")
        self.assertEqual(rows_rodilla[-1]["region_name"], "Rodilla")
        self.assertEqual(rows_rodilla[-1]["prompt_version"], "rodilla-1.0")
        self.assertEqual(rows_rodilla[-1]["validator_version"], "rodilla-1.0")
        for dataset in otras:
            if dataset.exists():
                self.assertNotIn("dolor de rodilla con condropatia patelar", dataset.read_text(encoding="utf-8"))

    def test_importador_enruta_abdomen_lumbar_cervical_rodilla_y_rechaza_region_ausente_o_desconocida(self):
        texto = """### CASO ###
[REGION]: abdomen
[BRUTO]:
dictado abdomen importado
[INFORME]:
Datos clínicos: dolor.
Hallazgos: sin hallazgos.
Impresión diagnóstica: sin hallazgos.
### FIN ###
### CASO ###
[REGION]: lumbar
[BRUTO]:
dictado lumbar importado
[INFORME]:
Datos clínicos: lumbalgia.
Hallazgos: sin estenosis.
Impresión diagnóstica: sin hallazgos agudos.
### FIN ###
### CASO ###
[REGION]: cervical
[BRUTO]:
dictado cervical importado
[INFORME]:
Datos clínicos: cervicalgia.
Exploración: RM columna cervical.
Hallazgos: protrusión paracentral C5-C6.
Impresión diagnóstica: protrusión paracentral C5-C6.
### FIN ###
### CASO ###
[REGION]: rodilla
[BRUTO]:
dictado rodilla importado
[INFORME]:
Datos clínicos: gonalgia.
Exploración: RM rodilla.
Hallazgos: meniscos de morfología conservada.
Impresión diagnóstica: sin hallazgos patológicos relevantes.
### FIN ###
### CASO ###
[BRUTO]:
dictado sin region
[INFORME]:
Informe sin region
### FIN ###
### CASO ###
[REGION]: torax
[BRUTO]:
dictado torax
[INFORME]:
Informe torax
### FIN ###"""
        response = self.client.post("/importar", json={"texto": texto})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["importados"], 5)
        estados = [(r["region"], r["estado"]) for r in data["resultados"]]
        self.assertIn(("abdomen", "importado"), estados)
        self.assertIn(("lumbar", "importado"), estados)
        self.assertIn(("cervical", "importado"), estados)
        self.assertIn(("rodilla", "importado"), estados)
        self.assertIn(("torax", "importado"), estados)
        self.assertIn(("", "error"), estados)
        self.assertNotIn(("torax", "error"), estados)
        self.assertIn("dictado abdomen importado", self.mod.get_region_config("abdomen").DATASET_PATH.read_text(encoding="utf-8"))
        self.assertIn("dictado lumbar importado", self.mod.get_region_config("lumbar").DATASET_PATH.read_text(encoding="utf-8"))
        self.assertIn("dictado cervical importado", self.mod.get_region_config("cervical").DATASET_PATH.read_text(encoding="utf-8"))
        self.assertIn("dictado rodilla importado", self.mod.get_region_config("rodilla").DATASET_PATH.read_text(encoding="utf-8"))
        self.assertIn("dictado torax", self.mod.get_region_config("torax").DATASET_PATH.read_text(encoding="utf-8"))

    def test_lumbar_conserva_receso_lateral_y_no_valida_indices_patelofemorales(self):
        self.client.post("/region", json={"region": "lumbar"})
        texto = (
            "Datos clínicos: lumbalgia.\n"
            "Hallazgos: estenosis del receso lateral izquierdo L4-L5. "
            "Insall-Salvati 1,234. Caton-Deschamps 1,234. TT-TG 18,55. CDI 1,22.\n"
            "Impresión diagnóstica: estenosis del receso lateral izquierdo L4-L5."
        )
        flags = self.mod.validar(texto)
        mensajes = " ".join(flag["mensaje"] for flag in flags).lower()

        self.assertNotIn("receso lateral", mensajes)
        self.assertNotIn("insall", mensajes)
        self.assertNotIn("caton", mensajes)
        self.assertNotIn("tt-tg", mensajes)
        self.assertNotIn("cdi", mensajes)

    def test_cervical_receso_lateral_y_posterolateral_generan_flags(self):
        self.client.post("/region", json={"region": "cervical"})
        texto = (
            "Datos clínicos: cervicalgia.\n"
            "Exploración: RM columna cervical.\n"
            "Hallazgos: hernia posterolateral C5-C6 con compromiso del receso lateral.\n"
            "Impresión diagnóstica: hernia posterolateral C5-C6."
        )

        reglas = {flag["regla"] for flag in self.mod.validar(texto)}

        self.assertIn("D2", reglas)
        self.assertIn("D3", reglas)

    def test_localizaciones_validas_cervicales_no_generan_flag_de_posterolateral(self):
        self.client.post("/region", json={"region": "cervical"})
        textos = [
            "Hernia central C5-C6.",
            "Hernia paracentral C5-C6.",
            "Hernia paracentral-foraminal derecha C5-C6.",
            "Hernia foraminal izquierda C5-C6.",
            "Hernia extraforaminal derecha C5-C6.",
        ]
        for texto in textos:
            with self.subTest(texto=texto):
                reglas = {flag["regla"] for flag in self.mod.validar(texto)}
                self.assertNotIn("D3", reglas)

    def test_pie_chileno_funciona_condicionalmente_en_cervical(self):
        self.client.post("/region", json={"region": "cervical"})
        con_formato_chileno = (
            "Datos clínicos: cervicalgia.\n"
            "FONASA: prueba.\n"
            "Hallazgos: sin hallazgos.\n"
            "Impresión diagnóstica: sin hallazgos."
        )
        sin_formato_chileno_con_pie = (
            "Datos clínicos: cervicalgia.\n"
            "Hallazgos: sin hallazgos.\n"
            "Impresión diagnóstica: sin hallazgos.\n"
            "Informado por Dr X.\n"
            "Validado por:"
        )
        sin_formato_chileno_sin_pie = (
            "Datos clínicos: cervicalgia.\n"
            "Hallazgos: sin hallazgos.\n"
            "Impresión diagnóstica: sin hallazgos."
        )

        self.assertIn("D1", {flag["regla"] for flag in self.mod.validar(con_formato_chileno)})
        self.assertIn("D1", {flag["regla"] for flag in self.mod.validar(sin_formato_chileno_con_pie)})
        self.assertNotIn("D1", {flag["regla"] for flag in self.mod.validar(sin_formato_chileno_sin_pie)})

    def test_terminos_patelofemorales_no_forman_parte_de_lumbar(self):
        terminos = ["Insall-Salvati", "Caton-Deschamps", "TT-TG", "CDI"]
        archivos = [
            Path(self.tmpdir.name) / "02_lumbar" / "SYSTEM_PROMPT_lumbar.txt",
            Path(self.tmpdir.name) / "02_lumbar" / "validador_lumbar.py",
            Path(self.tmpdir.name) / "02_lumbar" / "REGLAS_LUMBAR_MAESTRAS.md",
        ]
        for path in archivos:
            texto = path.read_text(encoding="utf-8").lower()
            for termino in terminos:
                self.assertNotIn(termino.lower(), texto)

    def test_gold_standard_lumbar_independiente_de_abdomen(self):
        self.client.post("/region", json={"region": "lumbar"})
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dictado lumbar validado",
                "informe_ia": "Informe lumbar limpio",
                "informe_final": "Informe lumbar limpio",
                "validacion_humana": True,
                "fecha_validacion": "2026-07-18T23:30:00.000Z",
                "validated_by": "radiologo",
                "case_status": "validated",
            },
        )
        self.assertEqual(response.status_code, 200)
        lumbar_record = json.loads(
            next(self.mod.CASOS_DIR.glob("caso_*.json")).read_text(encoding="utf-8")
        )
        self.assertEqual(lumbar_record["region"], "lumbar")
        self.assertTrue(lumbar_record["gold_standard"])

        self.client.post("/region", json={"region": "abdomen"})
        self.assertEqual(self.mod.current_region, "abdomen")
        self.assertFalse(self.mod._calcular_gold_standard(lumbar_record))

    def test_gold_standard_cervical_independiente(self):
        self.client.post("/region", json={"region": "cervical"})
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dictado cervical validado",
                "informe_ia": "Informe cervical limpio",
                "informe_final": "Informe cervical limpio",
                "validacion_humana": True,
                "fecha_validacion": "2026-07-18T23:45:00.000Z",
                "validated_by": "radiologo",
                "case_status": "validated",
            },
        )
        self.assertEqual(response.status_code, 200)
        cervical_record = json.loads(
            next(self.mod.CASOS_DIR.glob("caso_*.json")).read_text(encoding="utf-8")
        )
        self.assertEqual(cervical_record["region"], "cervical")
        self.assertTrue(cervical_record["gold_standard"])

        self.client.post("/region", json={"region": "abdomen"})
        self.assertFalse(self.mod._calcular_gold_standard(cervical_record))

    def test_rodilla_condropatia_romanos_y_normales_en_impresion(self):
        self.client.post("/region", json={"region": "rodilla"})
        texto_arabigo = (
            "Datos clínicos: gonalgia.\n"
            "Hallazgos: condropatía patelar grado 2.\n"
            "Impresión diagnóstica: condropatía patelar grado 2."
        )
        texto_romano = (
            "Datos clínicos: gonalgia.\n"
            "Hallazgos: condropatía patelar grado II.\n"
            "Impresión diagnóstica: condropatía patelar grado II."
        )
        impresion_normal = (
            "Datos clínicos: control.\n"
            "Hallazgos: meniscos de morfología conservada.\n"
            "Impresión diagnóstica: meniscos normales."
        )

        self.assertIn("D3", {flag["regla"] for flag in self.mod.validar(texto_arabigo)})
        self.assertNotIn("D3", {flag["regla"] for flag in self.mod.validar(texto_romano)})
        self.assertIn("D4", {flag["regla"] for flag in self.mod.validar(impresion_normal)})

    def test_rodilla_terminologia_meniscal_valida_no_genera_falsos_positivos(self):
        self.client.post("/region", json={"region": "rodilla"})
        texto = (
            "Datos clínicos: gonalgia.\n"
            "Hallazgos: rotura horizontal del cuerno posterior del menisco medial. "
            "Menisco lateral sin roturas.\n"
            "Impresión diagnóstica: rotura horizontal del cuerno posterior del menisco medial."
        )
        reglas = {flag["regla"] for flag in self.mod.validar(texto)}

        self.assertNotIn("D3", reglas)
        self.assertNotIn("D4", reglas)

    def test_indices_patelofemorales_no_son_obligatorios_y_si_aportados_no_bloquean(self):
        self.client.post("/region", json={"region": "rodilla"})
        rm_general = (
            "Datos clínicos: gonalgia.\n"
            "Hallazgos: meniscos y ligamentos sin roturas.\n"
            "Impresión diagnóstica: sin signos de rotura meniscal."
        )
        con_indices = (
            "Datos clínicos: inestabilidad patelofemoral.\n"
            "Hallazgos: Insall-Salvati 1,2. Caton-Deschamps 1,1. TT-TG 14 mm. CDI 1,0.\n"
            "Impresión diagnóstica: alineación patelofemoral conservada."
        )

        flags_general = self.mod.validar(rm_general)
        flags_indices = self.mod.validar(con_indices)
        mensajes = " ".join(flag["mensaje"] for flag in flags_general + flags_indices).lower()

        self.assertNotIn("insall", mensajes)
        self.assertNotIn("caton", mensajes)
        self.assertNotIn("tt-tg", mensajes)
        self.assertNotIn("cdi", mensajes)
        self.assertFalse(any(flag.get("bloquea_gold") for flag in flags_indices))

    def test_rodilla_no_hereda_reglas_cervicales_lumbares_ni_abdominales(self):
        self.client.post("/region", json={"region": "rodilla"})
        texto = (
            "Datos clínicos: gonalgia.\n"
            "Hallazgos: texto con posterolateral, receso lateral y 55 UH como datos incidentales del dictado.\n"
            "Impresión diagnóstica: lesión meniscal compleja."
        )
        reglas = {flag["regla"] for flag in self.mod.validar(texto)}
        mensajes = " ".join(flag["mensaje"] for flag in self.mod.validar(texto)).lower()

        self.assertNotIn("receso lateral", mensajes)
        self.assertNotIn("posterolateral", mensajes)
        self.assertNotIn("uh", mensajes)
        self.assertTrue(reglas.isdisjoint({"D8", "D9", "D10", "D11", "D12"}))

    def test_gold_standard_rodilla_independiente(self):
        self.client.post("/region", json={"region": "rodilla"})
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dictado rodilla validado",
                "informe_ia": "Informe rodilla limpio",
                "informe_final": "Informe rodilla limpio",
                "validacion_humana": True,
                "fecha_validacion": "2026-07-18T23:55:00.000Z",
                "validated_by": "radiologo",
                "case_status": "validated",
            },
        )
        self.assertEqual(response.status_code, 200)
        rodilla_record = json.loads(
            next(self.mod.CASOS_DIR.glob("caso_*.json")).read_text(encoding="utf-8")
        )
        self.assertEqual(rodilla_record["region"], "rodilla")
        self.assertTrue(rodilla_record["gold_standard"])

        self.client.post("/region", json={"region": "abdomen"})
        self.assertFalse(self.mod._calcular_gold_standard(rodilla_record))

    def test_mano_muneca_carga_rutas_y_estado_regional_independientes(self):
        response = self.client.post("/region", json={"region": "mano_muneca"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mod.current_region, "mano_muneca")
        self.assertEqual(self.mod.REGION_NAME, "Mano y muñeca")
        self.assertEqual(self.mod.PROMPT_VERSION, "mano_muneca-1.0")
        self.assertEqual(self.mod.VALIDATOR_VERSION, "mano_muneca-1.1")
        self.assertIn("casos_mano_muneca", str(self.mod.CASOS_DIR))
        self.assertIn("mano_muneca_dataset.jsonl", str(self.mod.DATASET))
        self.assertEqual(Path(self.mod.VALIDADOR_REGIONAL.__file__).name, "validador_mano_muneca.py")

        mano_prompt = self.mod.PROMPT_BASE + "\n- Override mano muñeca prueba"
        self.client.post("/guardar_prompt_borrador", json={"prompt": mano_prompt})
        applied = self.client.post("/aplicar_prompt").get_json()
        self.assertEqual(applied["prompt_version"], "mano_muneca-1.0+override.1")
        self.assertIn("06_mano_muneca", str(self.mod.CONFIG_PATH))
        self.assertIn("06_mano_muneca", str(self.mod.HISTORIAL_DIR))
        self.assertIn("06_mano_muneca", str(self.mod.REGLAS_CANDIDATAS))

        self.client.post("/region", json={"region": "abdomen"})
        self.assertNotIn("Override mano muñeca prueba", self.mod.SYSTEM_PROMPT)

    def test_mano_muneca_persistencia_y_gold_son_aislados(self):
        self.client.post("/region", json={"region": "mano_muneca"})
        mano_dataset = self.mod.DATASET
        otras = [self.mod.get_region_config(region).DATASET_PATH for region in ("abdomen", "lumbar", "cervical", "rodilla")]
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dolor de muñeca con sospecha de ganglión",
                "informe_ia": "Exploración: RM muñeca.\nHallazgos: túnel carpiano y canal de Guyon sin alteraciones.",
                "informe_final": "Exploración: RM muñeca.\nHallazgos: túnel carpiano y canal de Guyon sin alteraciones.",
                "modalidad": "RM",
                "validacion_humana": True,
                "case_status": "validated",
            },
        )

        self.assertEqual(response.status_code, 200)
        record = json.loads(next(self.mod.CASOS_DIR.glob("caso_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(record["region"], "mano_muneca")
        self.assertEqual(record["region_name"], "Mano y muñeca")
        self.assertEqual(record["modalidad"], "RM")
        self.assertTrue(record["gold_standard"])
        self.assertIn("dolor de muñeca", mano_dataset.read_text(encoding="utf-8"))
        for dataset in otras:
            if dataset.exists():
                self.assertNotIn("dolor de muñeca con sospecha de ganglión", dataset.read_text(encoding="utf-8"))

    def test_importador_mano_muneca_normaliza_alias_y_persiste_modalidad(self):
        texto = """### CASO ###
[REGION]: mano-muneca
[MODALIDAD]: RM
[BRUTO]:
dictado muñeca importado
[INFORME]:
Exploración: RM muñeca.
Hallazgos: túnel carpiano y canal de Guyon conservados.
### FIN ###
### CASO ###
[REGION]: mano muñeca
[BRUTO]:
dictado mano importado
[INFORME]:
Exploración: RM mano.
Hallazgos: nervio mediano y nervio cubital conservados.
### FIN ###"""
        response = self.client.post("/importar", json={"texto": texto})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["importados"], 2)
        self.assertTrue(all(item["region"] == "mano_muneca" for item in data["resultados"]))
        dataset = self.mod.get_region_config("mano_muneca").DATASET_PATH
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(rows[-2]["modalidad"], "RM")
        self.assertTrue(all(row["region"] == "mano_muneca" for row in rows[-2:]))

    def test_mano_muneca_checklist_respeta_campo_anatomico(self):
        self.client.post("/region", json={"region": "mano_muneca"})
        muneca_incompleta = "Exploración: RM muñeca.\nHallazgos: sin hallazgos relevantes."
        muneca_completa = (
            "Exploración: RM muñeca.\nHallazgos: túnel carpiano y canal de Guyon sin alteraciones."
        )
        dedo_limitado = "Exploración: RM dedo índice.\nHallazgos: falange distal sin fractura."

        reglas_incompleta = {flag["regla"] for flag in self.mod.validar(muneca_incompleta)}
        reglas_completa = {flag["regla"] for flag in self.mod.validar(muneca_completa)}
        flags_dedo = self.mod.validar(dedo_limitado)

        self.assertIn("B2", reglas_incompleta)
        self.assertNotIn("B2", reglas_completa)
        self.assertTrue({flag["regla"] for flag in flags_dedo}.isdisjoint({"B1", "B2"}))
        self.assertFalse(any(flag["bloquea_gold"] for flag in flags_dedo))

    def test_mano_muneca_cronicidad_es_conservadora_y_no_operacion_vacia(self):
        self.client.post("/region", json={"region": "mano_muneca"})
        valida = "Exploración: RM muñeca.\nCronicidad: postraumática.\nHallazgos: túnel carpiano y canal de Guyon conservados."
        invalida = "Exploración: RM muñeca.\nCronicidad: reciente.\nHallazgos: túnel carpiano y canal de Guyon conservados."
        libre = "Exploración: RM muñeca.\nHallazgos: cambios crónicos de baja entidad."
        ausente = "Exploración: RM muñeca.\nHallazgos: sin hallazgos relevantes."

        self.assertNotIn("D3", {flag["regla"] for flag in self.mod.validar(valida)})
        flags_invalidos = self.mod.validar(invalida)
        self.assertIn("D3", {flag["regla"] for flag in flags_invalidos})
        self.assertFalse(any(flag["bloquea_gold"] for flag in flags_invalidos))
        self.assertNotIn("D3", {flag["regla"] for flag in self.mod.validar(libre)})
        self.assertNotIn("D3", {flag["regla"] for flag in self.mod.validar(ausente)})

    def test_mano_muneca_no_hereda_reglas_de_columna_rodilla_abdomen_ni_torax(self):
        self.client.post("/region", json={"region": "mano_muneca"})
        texto = (
            "Exploración: RM mano.\nHallazgos: nervio mediano y nervio cubital conservados; "
            "receso lateral, TT-TG, Insall-Salvati y 55 UH constan solo en el dictado."
        )
        mensajes = " ".join(flag["mensaje"] for flag in self.mod.validar(texto)).lower()

        for termino in ("receso lateral", "tt-tg", "insall", "uh", "pulmonar", "hepatico"):
            self.assertNotIn(termino, mensajes)

    def test_codo_carga_componentes_y_estado_regional_independiente(self):
        response = self.client.post("/region", json={"region": "codo"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mod.current_region, "codo")
        self.assertEqual(self.mod.REGION_NAME, "Codo")
        self.assertEqual(self.mod.PROMPT_VERSION, "codo-1.0")
        self.assertEqual(self.mod.VALIDATOR_VERSION, "codo-1.1")
        self.assertIn("casos_codo", str(self.mod.CASOS_DIR))
        self.assertIn("codo_dataset.jsonl", str(self.mod.DATASET))
        self.assertEqual(Path(self.mod.VALIDADOR_REGIONAL.__file__).name, "validador_codo.py")

        prompt_codo = self.mod.PROMPT_BASE + "\n- Override codo prueba"
        self.client.post("/guardar_prompt_borrador", json={"prompt": prompt_codo})
        applied = self.client.post("/aplicar_prompt").get_json()
        self.assertEqual(applied["prompt_version"], "codo-1.0+override.1")
        self.assertIn("07_codo", str(self.mod.CONFIG_PATH))
        self.assertIn("07_codo", str(self.mod.HISTORIAL_DIR))
        self.assertIn("07_codo", str(self.mod.REGLAS_CANDIDATAS))

        self.client.post("/region", json={"region": "mano_muneca"})
        self.assertNotIn("Override codo prueba", self.mod.SYSTEM_PROMPT)

    def test_codo_persistencia_gold_y_importador_son_independientes(self):
        self.client.post("/region", json={"region": "codo"})
        codo_dataset = self.mod.DATASET
        otras = [self.mod.get_region_config(region).DATASET_PATH for region in (
            "abdomen", "lumbar", "cervical", "rodilla", "mano_muneca",
        )]
        informe = (
            "Exploración: RM codo derecho.\n"
            "Hallazgos: nervio cubital, nervio radial y nervio mediano conservados; "
            "tendón conjunto extensor, tendón conjunto flexor, bíceps distal y tríceps sin rotura."
        )
        response = self.client.post("/guardar", json={
            "caso": "dolor lateral de codo",
            "informe_ia": informe,
            "informe_final": informe,
            "modalidad": "RM",
            "validacion_humana": True,
            "case_status": "validated",
        })

        self.assertEqual(response.status_code, 200)
        record = json.loads(next(self.mod.CASOS_DIR.glob("caso_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(record["region"], "codo")
        self.assertEqual(record["region_name"], "Codo")
        self.assertEqual(record["modalidad"], "RM")
        self.assertTrue(record["gold_standard"])
        self.assertIn("dolor lateral de codo", codo_dataset.read_text(encoding="utf-8"))
        for dataset in otras:
            if dataset.exists():
                self.assertNotIn("dolor lateral de codo", dataset.read_text(encoding="utf-8"))

        importado = """### CASO ###
[REGION]: elbow
[MODALIDAD]: ecografía
[BRUTO]:
dictado codo importado
[INFORME]:
Exploración: ecografía codo.
Hallazgos: tendón conjunto extensor conservado.
### FIN ###"""
        data = self.client.post("/importar", json={"texto": importado}).get_json()
        self.assertEqual(data["importados"], 1)
        self.assertEqual(data["resultados"][0]["region"], "codo")
        self.assertIn("dictado codo importado", codo_dataset.read_text(encoding="utf-8"))

    def test_codo_medidas_de_biceps_conservan_unidades_y_avisan_solo_incoherencias(self):
        self.client.post("/region", json={"region": "codo"})
        con_cm = "Hallazgos: rotura completa del bíceps distal con retracción proximal de 8 cm."
        con_mm = "Hallazgos: rotura completa del bíceps distal con retracción proximal de 8 mm."
        sin_unidad = "Hallazgos: rotura completa del bíceps distal con retracción proximal de 8."
        sin_retraccion = "Hallazgos: rotura completa del bíceps distal."
        sin_rotura = "Hallazgos: tendón distal del bíceps conservado."
        discrepante = "Hallazgos: rotura completa del bíceps distal con retracción de 8 cm y retracción de 8 mm."

        self.assertIn("8 cm", con_cm)
        self.assertNotIn("D4", {flag["regla"] for flag in self.mod.validar(con_cm)})
        self.assertIn("8 mm", con_mm)
        self.assertNotIn("D4", {flag["regla"] for flag in self.mod.validar(con_mm)})
        self.assertIn("D4", {flag["regla"] for flag in self.mod.validar(sin_unidad)})
        self.assertIn("D4", {flag["regla"] for flag in self.mod.validar(sin_retraccion)})
        self.assertNotIn("D4", {flag["regla"] for flag in self.mod.validar(sin_rotura)})
        flags_discrepantes = self.mod.validar(discrepante)
        self.assertIn("D4", {flag["regla"] for flag in flags_discrepantes})
        self.assertFalse(any(flag["bloquea_gold"] for flag in flags_discrepantes))

    def test_codo_checklist_y_reglas_blancas_respetan_campo_y_contexto(self):
        self.client.post("/region", json={"region": "codo"})
        antebrazo = "Exploración: RM codo y antebrazo proximal.\nHallazgos: inserción distal del bíceps conservada."
        bilateral = (
            "Exploración: RM codos bilateral.\nHallazgos: codo derecho sin derrame. "
            "Codo izquierdo con leve tendinosis del conjunto extensor."
        )
        redundante = "Hallazgos: epicondilitis lateral con tendinosis del tendón conjunto extensor."
        no_redundante = "Hallazgos: epicondilitis lateral. Tendinosis del tendón conjunto flexor medial."
        postquirurgico = "Exploración: RM codo postquirúrgico. Hallazgos: fibrosis y material quirúrgico, sin signos de recidiva."
        sin_previos = "Exploración: RM codo. Sin estudios previos. Hallazgos: lesión estable respecto al control."

        flags_antebrazo = self.mod.validar(antebrazo)
        self.assertTrue({flag["regla"] for flag in flags_antebrazo}.isdisjoint({"B1", "B2"}))
        self.assertFalse(any(flag["bloquea_gold"] for flag in flags_antebrazo))
        self.assertNotIn("B4", {flag["regla"] for flag in self.mod.validar(bilateral)})
        self.assertIn("D3", {flag["regla"] for flag in self.mod.validar(redundante)})
        self.assertNotIn("D3", {flag["regla"] for flag in self.mod.validar(no_redundante)})
        self.assertNotIn("D5", {flag["regla"] for flag in self.mod.validar(postquirurgico)})
        self.assertIn("D5", {flag["regla"] for flag in self.mod.validar(sin_previos)})

    def test_codo_no_hereda_reglas_de_mano_rodilla_columna_abdomen_ni_torax(self):
        self.client.post("/region", json={"region": "codo"})
        texto = (
            "Exploración: RM codo.\nHallazgos: nervio cubital, radial y mediano; tendón conjunto extensor, "
            "conjunto flexor, bíceps distal y tríceps conservados. TFCC, canal de Guyon, TT-TG, receso lateral, "
            "55 UH y nódulo pulmonar constan solo en el dictado."
        )
        mensajes = " ".join(flag["mensaje"] for flag in self.mod.validar(texto)).lower()
        for termino in ("tfcc", "guyon", "tt-tg", "receso lateral", "uh", "pulmonar"):
            self.assertNotIn(termino, mensajes)

    def test_tobillo_pie_carga_componentes_y_estado_regional_independiente(self):
        response = self.client.post("/region", json={"region": "tobillo_pie"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mod.current_region, "tobillo_pie")
        self.assertEqual(self.mod.REGION_NAME, "Tobillo y pie")
        self.assertEqual(self.mod.PROMPT_VERSION, "tobillo_pie-1.0")
        self.assertEqual(self.mod.VALIDATOR_VERSION, "tobillo_pie-1.1")
        self.assertIn("casos_tobillo_pie", str(self.mod.CASOS_DIR))
        self.assertIn("tobillo_pie_dataset.jsonl", str(self.mod.DATASET))
        self.assertEqual(Path(self.mod.VALIDADOR_REGIONAL.__file__).name, "validador_tobillo_pie.py")

        prompt = self.mod.PROMPT_BASE + "\n- Override tobillo pie prueba"
        self.client.post("/guardar_prompt_borrador", json={"prompt": prompt})
        applied = self.client.post("/aplicar_prompt").get_json()
        self.assertEqual(applied["prompt_version"], "tobillo_pie-1.0+override.1")
        self.assertIn("08_tobillo_pie", str(self.mod.CONFIG_PATH))
        self.assertIn("08_tobillo_pie", str(self.mod.HISTORIAL_DIR))
        self.assertIn("08_tobillo_pie", str(self.mod.REGLAS_CANDIDATAS))

        self.client.post("/region", json={"region": "codo"})
        self.assertNotIn("Override tobillo pie prueba", self.mod.SYSTEM_PROMPT)

    def test_tobillo_pie_persistencia_gold_e_importador_son_independientes(self):
        self.client.post("/region", json={"region": "tobillo_pie"})
        dataset = self.mod.DATASET
        otras = [self.mod.get_region_config(region).DATASET_PATH for region in (
            "abdomen", "lumbar", "cervical", "rodilla", "mano_muneca", "codo",
        )]
        informe = (
            "Exploración: RM tobillo derecho.\nHallazgos: Aquiles, peroneos, tibial posterior, "
            "flexor largo del primer dedo, flexor largo de los dedos, complejo lateral, deltoideo, "
            "seno del tarso y fascia plantar conservados."
        )
        response = self.client.post("/guardar", json={
            "caso": "dolor de tobillo derecho",
            "informe_ia": informe,
            "informe_final": informe,
            "modalidad": "RM",
            "validacion_humana": True,
            "case_status": "validated",
        })
        self.assertEqual(response.status_code, 200)
        record = json.loads(next(self.mod.CASOS_DIR.glob("caso_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(record["region"], "tobillo_pie")
        self.assertEqual(record["region_name"], "Tobillo y pie")
        self.assertEqual(record["modalidad"], "RM")
        self.assertTrue(record["gold_standard"])
        for otro in otras:
            if otro.exists():
                self.assertNotIn("dolor de tobillo derecho", otro.read_text(encoding="utf-8"))

        texto = """### CASO ###
[REGION]: tobillo-pie
[MODALIDAD]: TC
[BRUTO]:
dictado tobillo importado
[INFORME]:
Exploración: TC tobillo.
Hallazgos: sin fractura aguda.
### FIN ###
### CASO ###
[REGION]: pie_tobillo
[BRUTO]:
dictado pie importado
[INFORME]:
Exploración: ecografía pie.
Hallazgos: sin colecciones.
### FIN ###"""
        data = self.client.post("/importar", json={"texto": texto}).get_json()
        self.assertEqual(data["importados"], 2)
        self.assertTrue(all(item["region"] == "tobillo_pie" for item in data["resultados"]))
        self.assertIn("dictado tobillo importado", dataset.read_text(encoding="utf-8"))

    def test_tobillo_pie_terminologia_causalidad_y_fascia_son_conservadoras(self):
        self.client.post("/region", json={"region": "tobillo_pie"})
        bursatil = "Hallazgos: distensión bursátil en el segundo espacio."
        bursa_correcta = "Hallazgos: distensión de la bursa intermetatarsiana en el segundo espacio."
        os_correcto = "Hallazgos: os trigonum con signos de pinzamiento posterior."
        os_invertido = "Hallazgos: pinzamiento posterior asociado a un os trigonum."
        medida_hallazgos = "Hallazgos: fascitis plantar con grosor de 6 mm.\nImpresión diagnóstica: fascitis plantar."
        medida_impresion = "Hallazgos: fascitis plantar.\nImpresión diagnóstica: fascitis plantar de 6 mm."

        self.assertIn("D2", {flag["regla"] for flag in self.mod.validar(bursatil)})
        self.assertNotIn("D2", {flag["regla"] for flag in self.mod.validar(bursa_correcta)})
        self.assertNotIn("D3", {flag["regla"] for flag in self.mod.validar(os_correcto)})
        self.assertIn("D3", {flag["regla"] for flag in self.mod.validar(os_invertido)})
        self.assertNotIn("D5", {flag["regla"] for flag in self.mod.validar(medida_hallazgos)})
        self.assertIn("D5", {flag["regla"] for flag in self.mod.validar(medida_impresion)})

    def test_tobillo_pie_responde_a_subregion_modalidad_y_lisfranc(self):
        self.client.post("/region", json={"region": "tobillo_pie"})
        tobillo_limitado = "Exploración: RM tobillo.\nHallazgos: Aquiles conservado."
        pie = "Exploración: RM mediopié.\nHallazgos: sin edema óseo."
        aquiles_focal = "Exploración: RM estudio focal de Aquiles.\nHallazgos: tendón de Aquiles conservado."
        dedo = "Exploración: RM dedo del pie.\nHallazgos: falange distal sin fractura."
        ecografia = "Exploración: ecografía tobillo.\nHallazgos: tendones peroneos conservados."
        sin_carga = "Hallazgos: Lisfranc sin carga, sin inestabilidad."
        fhl_fisiologico = "Hallazgos: flexor largo del primer dedo con líquido fisiológico, compatible con tenosinovitis."
        fhl_fisiologico_sin_tenosinovitis = "Hallazgos: flexor largo del primer dedo con líquido fisiológico, sin signos de tenosinovitis."

        self.assertNotIn("B1", {flag["regla"] for flag in self.mod.validar(tobillo_limitado)})
        self.assertIn("B1", {flag["regla"] for flag in self.mod.validar(pie)})
        self.assertTrue({flag["regla"] for flag in self.mod.validar(aquiles_focal)}.isdisjoint({"B1", "B2", "B3"}))
        self.assertTrue({flag["regla"] for flag in self.mod.validar(dedo)}.isdisjoint({"B1", "B2", "B3"}))
        self.assertTrue({flag["regla"] for flag in self.mod.validar(ecografia)}.isdisjoint({"B1", "B2", "B3"}))
        self.assertIn("B6", {flag["regla"] for flag in self.mod.validar(sin_carga)})
        self.assertIn("B7", {flag["regla"] for flag in self.mod.validar(fhl_fisiologico)})
        self.assertNotIn("B7", {flag["regla"] for flag in self.mod.validar(fhl_fisiologico_sin_tenosinovitis)})

    def test_tobillo_pie_complejo_lateral_y_aislamiento_clinico(self):
        self.client.post("/region", json={"region": "tobillo_pie"})
        lateral_incompleto = "Exploración: RM tobillo.\nHallazgos: rotura del complejo lateral con afectación del LPAA."
        lateral_completo = "Exploración: RM tobillo.\nHallazgos: lesión del LPAA, LPC y LPAP."
        texto = (
            "Exploración: RM tobillo.\nHallazgos: Aquiles, peroneos, tibial posterior, flexor largo del primer dedo, "
            "flexor largo de los dedos, complejo lateral, deltoideo, seno del tarso y fascia plantar conservados. "
            "TFCC, canal de Guyon, TT-TG, bíceps distal y receso lateral constan solo en el dictado."
        )

        self.assertIn("B4", {flag["regla"] for flag in self.mod.validar(lateral_incompleto)})
        self.assertNotIn("B4", {flag["regla"] for flag in self.mod.validar(lateral_completo)})
        mensajes = " ".join(flag["mensaje"] for flag in self.mod.validar(texto)).lower()
        for termino in ("tfcc", "guyon", "tt-tg", "biceps", "receso lateral"):
            self.assertNotIn(termino, mensajes)

    def test_torax_carga_configuracion_selector_y_aislamiento_de_prompt(self):
        response = self.client.post("/region", json={"region": "torax"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mod.current_region, "torax")
        self.assertEqual(self.mod.REGION_NAME, "Tórax")
        self.assertEqual(self.mod.PROMPT_VERSION, "torax-1.0")
        self.assertEqual(self.mod.VALIDATOR_VERSION, "torax-1.0")
        self.assertIn("casos_torax", str(self.mod.CASOS_DIR))
        self.assertIn("torax_dataset.jsonl", str(self.mod.DATASET))
        self.assertEqual(Path(self.mod.VALIDADOR_REGIONAL.__file__).name, "validador_torax.py")
        self.assertIn("angio_tc_tep", self.mod.REGION_CONFIG.STUDY_TYPES)
        self.assertIn("torax_abdomen_pelvis", self.mod.REGION_CONFIG.STUDY_TYPES)

        prompt = self.mod.PROMPT_BASE + "\n- Override torax prueba"
        self.client.post("/guardar_prompt_borrador", json={"prompt": prompt})
        applied = self.client.post("/aplicar_prompt").get_json()
        self.assertEqual(applied["prompt_version"], "torax-1.0+override.1")
        self.assertIn("04_torax", str(self.mod.CONFIG_PATH))
        self.assertIn("04_torax", str(self.mod.HISTORIAL_DIR))
        self.assertIn("04_torax", str(self.mod.REGLAS_CANDIDATAS))

        self.client.post("/region", json={"region": "abdomen"})
        self.assertNotIn("Override torax prueba", self.mod.SYSTEM_PROMPT)

    def test_torax_validador_aplica_perfiles_sin_reglas_cruzadas(self):
        self.client.post("/region", json={"region": "torax"})
        general = "Exploración: TC tórax sin contraste.\nHallazgos: nódulo pulmonar de 4 mm."
        tep = "Exploración: Angio-TC TEP.\nHallazgos: arterias pulmonares sin defectos de repleción. VD/VI 0,8 sin sobrecarga derecha."
        tep_suboptimo = "Exploración: Angio-TC TEP.\nHallazgos: opacificación subóptima de arterias pulmonares."
        cribado_fuera = general + " Lung-RADS 2."
        oncologico_sin_previo = "Hallazgos: lesión estable."
        contaminado = "Hallazgos: PieloTC por urolitiasis."

        self.assertTrue({flag["regla"] for flag in self.mod.validar(general, {"study_type": "tc_torax"})}.isdisjoint({"T3", "T6"}))
        self.assertFalse(any(flag["bloquea_gold"] for flag in self.mod.validar(tep, {"study_type": "angio_tc_tep", "protocol": "angiografico_pulmonar"})))
        self.assertIn("T6", {flag["regla"] for flag in self.mod.validar(tep_suboptimo, {"study_type": "angio_tc_tep", "protocol": "angiografico_pulmonar"})})
        self.assertIn("T7", {flag["regla"] for flag in self.mod.validar(cribado_fuera, {"study_type": "tc_torax"})})
        self.assertIn("T8", {flag["regla"] for flag in self.mod.validar(oncologico_sin_previo, {"clinical_context": "oncologico", "comparison_available": False})})
        flags_contaminados = self.mod.validar(contaminado, {"study_type": "tc_torax"})
        self.assertTrue(any(flag["regla"] == "T5" and flag["bloquea_gold"] for flag in flags_contaminados))

    def test_torax_tap_y_tep_aplican_solo_bloqueos_estructurales(self):
        self.client.post("/region", json={"region": "torax"})
        tap_incompleto = "Hallazgos: pulmones sin consolidaciones. Hígado sin lesiones focales."
        tap_completo = "Hallazgos: pulmones sin consolidaciones. Hígado sin lesiones focales. Vejiga sin alteraciones."
        tep_sin_arterias = "Hallazgos: parénquima pulmonar sin consolidaciones."
        protocolo_incoherente = "Hallazgos: arterias pulmonares sin defectos de repleción."

        flags_tap = self.mod.validar(tap_incompleto, {"study_type": "torax_abdomen_pelvis", "protocol": "tap"})
        self.assertTrue(any(flag["regla"] == "T4" and flag["bloquea_gold"] for flag in flags_tap))
        self.assertNotIn("T4", {flag["regla"] for flag in self.mod.validar(tap_completo, {"study_type": "torax_abdomen_pelvis", "protocol": "tap"})})
        self.assertTrue(any(flag["regla"] == "T3" and flag["bloquea_gold"] for flag in self.mod.validar(tep_sin_arterias, {"study_type": "angio_tc_tep", "protocol": "angiografico_pulmonar"})))
        self.assertTrue(any(flag["regla"] == "T2" and flag["bloquea_gold"] for flag in self.mod.validar(protocolo_incoherente, {"study_type": "angio_tc_tep", "protocol": "sin_contraste"})))
        self.assertTrue(any(flag["regla"] == "T1" and flag["bloquea_gold"] for flag in self.mod.validar("Hallazgos: sin hallazgos.", {"study_type": "desconocido"})))

    def test_torax_persistencia_dataset_gold_e_importador_son_aislados(self):
        self.client.post("/region", json={"region": "torax"})
        dataset = self.mod.DATASET
        abdomen_dataset = self.mod.get_region_config("abdomen").DATASET_PATH
        informe = "Exploración: TC tórax.\nHallazgos: nódulo pulmonar subcentimétrico sin derrame pleural."
        response = self.client.post("/guardar", json={
            "caso": "tos persistente",
            "informe_ia": informe,
            "informe_final": informe,
            "modalidad": "TC",
            "study_type": "tc_torax",
            "clinical_context": "general",
            "protocol": "sin_contraste",
            "contrast": "sin_contraste",
            "comparison_available": False,
            "validacion_humana": True,
            "case_status": "validated",
        })

        self.assertEqual(response.status_code, 200)
        record = json.loads(next(self.mod.CASOS_DIR.glob("caso_*.json")).read_text(encoding="utf-8"))
        self.assertEqual(record["region"], "torax")
        self.assertEqual(record["study_type"], "tc_torax")
        self.assertEqual(record["clinical_context"], "general")
        self.assertEqual(record["protocol"], "sin_contraste")
        self.assertEqual(record["validation_status"], "validated")
        self.assertTrue(record["gold_status"])
        self.assertTrue(record["gold_standard"])
        if abdomen_dataset.exists():
            self.assertNotIn("tos persistente", abdomen_dataset.read_text(encoding="utf-8"))

        texto = """### CASO ###
[REGION]: AngioTC TEP
[CLINICAL_CONTEXT]: trauma
[BRUTO]:
sospecha de embolia pulmonar
[INFORME]:
Exploración: Angio-TC pulmonar.
Hallazgos: arterias pulmonares sin defectos de repleción.
### FIN ###
### CASO ###
[REGION]: TAP
[BRUTO]:
seguimiento oncológico
[INFORME]:
Hallazgos: pulmones sin lesiones. Hígado sin lesiones. Vejiga sin alteraciones.
### FIN ###"""
        data = self.client.post("/importar", json={"texto": texto}).get_json()
        self.assertEqual(data["importados"], 2)
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(rows[-2]["study_type"], "angio_tc_tep")
        self.assertEqual(rows[-1]["study_type"], "torax_abdomen_pelvis")
        self.assertEqual(rows[-2]["clinical_context"], "trauma")

    def test_torax_aliases_y_metadatos_normalizan_sin_inventar_clasificaciones(self):
        aliases = {
            "torax": "tc_torax",
            "tc torax": "tc_torax",
            "tac torax": "tc_torax",
            "angiotc tep": "angio_tc_tep",
            "angio tc pulmonar": "angio_tc_tep",
            "tep": "angio_tc_tep",
            "screening pulmonar": "cribado_pulmonar",
            "cribado": "cribado_pulmonar",
            "tap": "torax_abdomen_pelvis",
            "torax abdomen pelvis": "torax_abdomen_pelvis",
        }
        for alias, study_type in aliases.items():
            with self.subTest(alias=alias):
                self.assertEqual(self.mod._normalizar_region_importada(alias), "torax")
                self.assertEqual(self.mod._metadatos_torax({}, alias)["study_type"], study_type)

    def test_health_informa_ocho_regiones_y_estado_de_proveedor_sin_llama_server(self):
        self.mod.DEFAULT_PROVIDER = "mock"
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["region_count"], 8)
        self.assertEqual(data["registered_regions"][-1], "torax")
        self.assertTrue(data["data_dir_writable"])
        self.assertTrue(data["gold_storage_available"])
        self.assertEqual(data["active_provider"], "mock")

    def test_detector_regional_reconoce_las_ocho_regiones_con_evidencia_explicita(self):
        casos = {
            "abdomen": "TC de abdomen: hígado, páncreas y bazo sin alteraciones.",
            "lumbar": "RM lumbar: cambios degenerativos en L4-L5 y L5-S1.",
            "cervical": "RM cervical con protrusión en C5-C6.",
            "rodilla": "RM de rodilla: rotura del menisco medial.",
            "mano_muneca": "RM de muñeca con edema del escafoides.",
            "codo": "RM de codo con tendinopatía del epicóndilo lateral.",
            "tobillo_pie": "RM de tobillo: tendón de Aquiles y fascia plantar.",
            "torax": "TC de tórax: nódulo pulmonar y derrame pleural.",
        }
        for region, texto in casos.items():
            with self.subTest(region=region):
                deteccion = self.mod.detectar_region_desde_texto(texto)
                self.assertEqual(deteccion["region"], region)
                self.assertEqual(deteccion["confidence"], "high")

    def test_detector_regional_mantiene_la_confirmacion_ante_ambiguedad(self):
        deteccion = self.mod.detectar_region_desde_texto("Dolor de rodilla y tobillo tras caída.")

        self.assertEqual(deteccion["confidence"], "uncertain")
        self.assertIn(deteccion["region"], {"rodilla", "tobillo_pie"})

    def test_ruta_detector_region_devuelve_confirmacion_para_texto_no_clasificable(self):
        response = self.client.post("/detectar_region", json={"caso": "Control radiológico sin más datos."})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["confidence"], "uncertain")
        self.assertIsNone(response.get_json()["region"])

    def test_health_llama_no_disponible_es_degradado_sin_caer(self):
        self.mod.DEFAULT_PROVIDER = "llama_cpp"
        with patch.object(self.mod, "_llama_provider") as provider_factory:
            provider = MagicMock()
            provider.is_configured.return_value = True
            provider.get_model_name.return_value = "modelo-local"
            provider.health_check.return_value = {"reachable": False, "error_code": "provider_unreachable"}
            provider_factory.return_value = provider
            response = self.client.get("/health")

        data = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "degraded")
        self.assertFalse(data["provider_reachable"])
        self.assertEqual(data["provider_error_code"], "provider_unreachable")

    def test_health_consulta_el_proveedor_solicitado(self):
        self.mod.DEFAULT_PROVIDER = "mock"
        with patch.object(self.mod, "_llama_provider") as provider_factory:
            provider = MagicMock()
            provider.is_configured.return_value = True
            provider.get_model_name.return_value = "modelo-local"
            provider.health_check.return_value = {"reachable": False, "error_code": "provider_unreachable"}
            provider_factory.return_value = provider
            response = self.client.get("/health?provider=llama_cpp")

        data = response.get_json()
        self.assertEqual(data["active_provider"], "llama_cpp")
        self.assertEqual(data["status"], "degraded")
        self.assertFalse(data["provider_reachable"])

    def test_metadatos_llama_cpp_se_persisten_sin_secretos_y_no_son_gold_por_defecto(self):
        response = self.client.post("/guardar", json={
            "caso": "caso sintetico local",
            "informe_ia": "Informe local",
            "informe_final": "Informe local",
            "provider": "llama_cpp",
            "model": "modelo-local",
            "case_status": "generated",
            "generation_metadata": {
                "provider": "llama_cpp",
                "model": "modelo-local",
                "base_url": "http://127.0.0.1:8080",
                "latency_ms": 42,
                "status": "success",
                "token_usage": {"completion_tokens": 10},
                "api_key": "secreto-que-no-debe-guardarse",
            },
        })

        self.assertEqual(response.status_code, 200)
        record = json.loads(next(self.mod.CASOS_DIR.glob("caso_*.json")).read_text(encoding="utf-8"))
        metadata = record["generation_metadata"]
        self.assertEqual(record["proveedor"], "llama_cpp")
        self.assertEqual(metadata["latency_ms"], 42)
        self.assertNotIn("api_key", metadata)
        self.assertFalse(record["gold_standard"])

    def test_guardar_rechaza_informe_final_vacio_con_flag_bloqueante(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dictado bruto",
                "informe_ia": "Informe IA",
                "informe_final": "   ",
                "correccion": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        flags = response.get_json()["flags"]
        self.assertTrue(any(flag["regla"] == "FINAL_EMPTY" and flag["bloquea_gold"] for flag in flags))

    def test_estado_rejected_se_persiste_y_no_es_gold(self):
        response = self.client.post(
            "/guardar",
            json={
                "caso": "dictado bruto rechazado",
                "informe_ia": "Informe IA",
                "informe_final": "Informe final",
                "correccion": "rechazado por el radiologo",
                "validacion_humana": True,
                "case_status": "rejected",
            },
        )

        self.assertEqual(response.status_code, 200)
        case_id = response.get_json()["archivo"].replace("caso_", "")
        record = json.loads(
            (self.mod.CASOS_DIR / f"caso_{case_id}.json").read_text(encoding="utf-8")
        )
        self.assertEqual(record["case_status"], "rejected")
        self.assertFalse(record["gold_standard"])


if __name__ == "__main__":
    unittest.main()
