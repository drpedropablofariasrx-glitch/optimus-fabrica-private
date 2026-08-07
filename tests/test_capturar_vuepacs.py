import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "capturar_vuepacs.py"
SPEC = importlib.util.spec_from_file_location("capturar_vuepacs", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


REPORT = """Origen:

Información Clínica

Exploración
RM DE RODILLA SIN CONTRASTE

Descripción:
Datos clínicos: dolor mecánico.

Exploración: RM de rodilla.

Hallazgos:
Meniscos y ligamentos cruzados sin alteraciones. No se observa derrame articular.

Impresión diagnóstica:
Sin hallazgos patológicos significativos.

Dr: Nombre Apellido, a día: 21/07/2026 12:53:02
"""


REPORT_NO_IMPRESSION = """Origen:

Información Clínica

Exploración
RM DE HOMBRO SIN CONTRASTE

Descripción:
Datos clínicos: dolor de hombro tras caída banal.

Exploración: RM de hombro.

Hallazgos:
Tendón supraespinoso íntegro. Sin signos de rotura tendinosa ni derrame
articular relevante. Estructuras óseas sin alteraciones agudas.

Dr: Nombre Ficticio, a día: 22/07/2026 09:10:00
"""


REPORT_HEADERS_WITHOUT_COLON = """Exploración
TC CRANEO SIN CONTRASTE

Descripción:
Datos clínicos
Paciente ficticio con cefalea de una semana de evolución, sin fiebre ni
focalidad neurológica asociada.

Exploración
TC craneal sin contraste.

Hallazgos

Sin alteraciones agudas. Estructuras de la línea media conservadas. Sin
colecciones ni focos hemorrágicos.

Impresión diagnóstica

Estudio sin hallazgos agudos significativos.

Dr: Nombre Ficticio2, a día: 01/03/2026 10:00:00
"""


REPORT_NO_BODY_EXPLORATION_WITH_CONCLUSION = """Exploración
TC ABDOMEN Y PELVIS SIN CONTRASTE

Descripción:
Datos clínicos
Paciente ficticio con dolor abdominal difuso de dos días de evolución.

Hallazgos

Hígado, bazo y páncreas de morfología y densidad conservadas. Sin
colecciones ni líquido libre significativo.

Conclusión

Estudio abdominal sin hallazgos agudos.

Dr: Nombre Ficticio3, a día: 15/03/2026 11:30:00
"""


class FakePoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class FakeRect:
    def __init__(self, x, y):
        self._point = FakePoint(x, y)

    def mid_point(self):
        return self._point


class FakeItem:
    def __init__(self, text="Ver informes", exists=True, rect=None):
        self._text = text
        self._exists = exists
        self._rect = rect
        self.invoked = False
        self.selected = False

    def text(self):
        return self._text

    def exists(self, timeout=0):
        return self._exists

    def wrapper_object(self):
        return self

    def invoke(self):
        self.invoked = True

    def select(self):
        self.selected = True

    def rectangle(self):
        if self._rect is None:
            raise AttributeError("sin rectangulo en esta prueba")
        return self._rect


class FakeUiaMenu:
    def __init__(self, item):
        self.item = item

    def child_window(self, **kwargs):
        return self.item


class FakeWin32Popup:
    def __init__(self, items):
        self._items = items

    def menu(self):
        return self

    def items(self):
        return self._items


class FakeDesktop:
    def __init__(self, windows):
        self._windows = windows
        self.windowed_handles = []

    def windows(self, **kwargs):
        return self._windows

    def window(self, handle=None, **kwargs):
        self.windowed_handles.append(handle)
        return FakeWindowFull(handle=handle, class_name="Explorador de informes")


class FakeMainWindow:
    def __init__(self, process_id):
        self._process_id = process_id

    def process_id(self):
        return self._process_id


class FakeMouse:
    def __init__(self):
        self.clicks = []
        self.moves = []
        self.presses = []
        self.releases = []

    def click(self, **kwargs):
        self.clicks.append(kwargs)

    def move(self, **kwargs):
        self.moves.append(kwargs)

    def press(self, **kwargs):
        self.presses.append(kwargs)

    def release(self, **kwargs):
        self.releases.append(kwargs)


class FakeWindow:
    def __init__(self, class_name="Dialog", raise_on_class_name=False):
        self._class_name = class_name
        self._raise = raise_on_class_name

    def class_name(self):
        if self._raise:
            raise AttributeError("sin class_name")
        return self._class_name


class FakeWindowFull:
    """Ventana falsa completa para probar _open_report de punta a punta."""

    def __init__(self, handle, class_name="WindowsForms10.Window.8.app.0"):
        self.handle = handle
        self._class_name = class_name
        self.closed = False

    def is_visible(self):
        return True

    def class_name(self):
        return self._class_name

    def close(self):
        self.closed = True


class FakeDesktopSequence:
    """desktop_uia.windows() que devuelve una lista distinta por llamada."""

    def __init__(self, sequence):
        self._sequence = list(sequence)
        self._last = sequence[-1] if sequence else []

    def windows(self, **kwargs):
        if self._sequence:
            return self._sequence.pop(0)
        return self._last


class CapturarVuePacsTests(unittest.TestCase):
    @patch.object(MODULE, "_process_id_at_point", return_value=1234)
    @patch.object(MODULE, "_visual_report_menu_target", return_value=((80, 90), 0.95))
    def test_visual_target_is_verified_against_vue_process(
        self, _visual_target, _process_at_point
    ):
        target, score = MODULE._verified_visual_report_target(FakeMainWindow(1234))

        self.assertEqual(target, (80, 90))
        self.assertEqual(score, 0.95)

    @patch.object(MODULE, "_process_id_at_point", return_value=9999)
    @patch.object(MODULE, "_visual_report_menu_target", return_value=((80, 90), 0.95))
    def test_visual_target_outside_vue_is_rejected(
        self, _visual_target, _process_at_point
    ):
        with self.assertRaisesRegex(MODULE.CaptureError, "no pertenece a Vue PACS"):
            MODULE._verified_visual_report_target(FakeMainWindow(1234))

    def test_visual_template_finds_sanitized_menu_item(self):
        from PIL import Image

        for template_path in MODULE.REPORT_MENU_TEMPLATE_PATHS:
            with self.subTest(template=template_path.name):
                template = Image.open(template_path).convert("RGB")
                screen = Image.new("RGB", (500, 200), color=(90, 90, 90))
                screen.paste(template, (120, 70))

                target, score = MODULE._visual_report_menu_target(
                    screen=screen, virtual_origin=(0, 0)
                )

                self.assertGreater(score, 0.99)
                self.assertLessEqual(score, 1.0)
                self.assertEqual(
                    target,
                    (120 + template.width // 2, 70 + template.height // 2),
                )

    @patch.object(MODULE, "_cursor_position_and_process_id", return_value=((20, 30), 1234))
    def test_right_click_is_allowed_only_over_vue(self, _cursor_info):
        mouse = FakeMouse()

        MODULE._right_click_vue_at_cursor(FakeMainWindow(1234), mouse)

        self.assertEqual(mouse.clicks, [{"button": "right", "coords": (20, 30)}])

    @patch.object(MODULE, "_cursor_position_and_process_id", return_value=((20, 30), 9999))
    def test_right_click_stops_outside_vue(self, _cursor_info):
        mouse = FakeMouse()

        with self.assertRaisesRegex(MODULE.CaptureError, "no está sobre Vue PACS"):
            MODULE._right_click_vue_at_cursor(FakeMainWindow(1234), mouse)

        self.assertEqual(mouse.clicks, [])

    @patch.object(MODULE, "_stop_pressed", return_value=False)
    def test_menu_lookup_records_nonclinical_diagnostics(self, _stop_pressed):
        diagnostics = {}

        match = MODULE._find_report_menu_item(
            FakeDesktop([]),
            FakeDesktop([]),
            timeout=0.01,
            diagnostics=diagnostics,
        )

        self.assertIsNone(match)
        self.assertEqual(
            diagnostics,
            {
                "uia_menu_windows": 0,
                "uia_descendant_items": 0,
                "win32_popups": 0,
                "win32_descendant_popups": 0,
            },
        )

    @patch.object(MODULE, "_foreground_process_id", return_value=1234)
    def test_focus_guard_accepts_vue_process(self, _foreground_process_id):
        MODULE._require_vue_focus(FakeMainWindow(1234))

    @patch.object(MODULE, "_foreground_process_id", return_value=9999)
    def test_focus_guard_rejects_other_process(self, _foreground_process_id):
        with self.assertRaisesRegex(MODULE.CaptureError, "no tiene el foco"):
            MODULE._require_vue_focus(FakeMainWindow(1234))

    @patch.object(MODULE, "_stop_pressed", return_value=False)
    def test_menu_lookup_falls_back_to_exact_win32_item(self, _stop_pressed):
        hidden_uia_item = FakeItem(exists=False)
        wrong_item = FakeItem("Crear otro informe para el estudio")
        report_item = FakeItem()

        match = MODULE._find_report_menu_item(
            FakeDesktop([FakeUiaMenu(hidden_uia_item)]),
            FakeDesktop([FakeWin32Popup([wrong_item, report_item])]),
            timeout=0.2,
        )

        self.assertEqual(match, ("win32", report_item))
        self.assertFalse(report_item.selected)
        self.assertFalse(report_item.invoked)

    def test_window_classes_reports_class_names_not_titles(self):
        windows = [FakeWindow("SunAwtDialog"), FakeWindow("#32770")]

        self.assertEqual(MODULE._window_classes(windows), ["SunAwtDialog", "#32770"])

    def test_window_classes_falls_back_when_class_name_unavailable(self):
        windows = [FakeWindow(raise_on_class_name=True)]

        self.assertEqual(MODULE._window_classes(windows), ["?"])

    @patch.object(MODULE, "_window_rect")
    def test_window_content_click_point_is_biased_toward_lower_panel(self, _rect):
        _rect.return_value = (100, 200, 900, 1200)  # ancho=800, alto=1000

        point = MODULE._window_content_click_point(42)

        self.assertEqual(point, (500, 800))  # centro x, 60% de la altura

    @patch.object(MODULE, "_window_rect", return_value=None)
    def test_window_content_click_point_is_none_when_rect_unavailable(self, _rect):
        self.assertIsNone(MODULE._window_content_click_point(42))

    @patch.object(MODULE, "_window_descendant_count")
    @patch.object(MODULE, "_window_total_child_text_length")
    @patch.object(MODULE, "_window_rect_area", return_value=500000)
    def test_select_report_window_by_content_prefers_text_length(
        self, _area, _text_length, _descendants
    ):
        new_a = FakeWindowFull(handle=2, class_name="Alfa")
        new_b = FakeWindowFull(handle=3, class_name="Beta")
        _text_length.side_effect = lambda handle: {2: 0, 3: 200}[handle]
        _descendants.side_effect = lambda handle: {2: 5, 3: 5}[handle]

        chosen, metrics = MODULE._select_report_window_by_content([new_a, new_b])

        self.assertIs(chosen, new_b)
        self.assertEqual(len(metrics), 2)

    @patch.object(MODULE, "_window_descendant_count")
    @patch.object(MODULE, "_window_total_child_text_length", return_value=0)
    @patch.object(MODULE, "_window_rect_area", return_value=500000)
    def test_select_report_window_by_content_falls_back_to_descendant_count(
        self, _area, _text_length, _descendants
    ):
        # Reproduce el caso real: el informe se ve completo en pantalla
        # (pestanas, texto) pero GetWindowTextLength devuelve 0 porque el
        # contenido esta en un control que no expone texto por Win32 (por
        # ejemplo un visor HTML embebido). Como ninguna ventana tiene
        # longitud de texto, se decide por la cantidad de controles hijos.
        new_a = FakeWindowFull(handle=2, class_name="Alfa")  # vacia/de carga
        new_b = FakeWindowFull(handle=3, class_name="Beta")  # con la UI real
        _descendants.side_effect = lambda handle: {2: 1, 3: 14}[handle]

        chosen, metrics = MODULE._select_report_window_by_content([new_a, new_b])

        self.assertIs(chosen, new_b)
        self.assertEqual(len(metrics), 2)

    @patch.object(MODULE, "_window_descendant_count")
    @patch.object(MODULE, "_window_total_child_text_length", return_value=0)
    @patch.object(MODULE, "_window_rect_area", return_value=500000)
    def test_select_report_window_by_content_returns_none_when_too_similar(
        self, _area, _text_length, _descendants
    ):
        new_a = FakeWindowFull(handle=2, class_name="Alfa")
        new_b = FakeWindowFull(handle=3, class_name="Beta")
        _descendants.side_effect = lambda handle: {2: 10, 3: 11}[handle]

        chosen, metrics = MODULE._select_report_window_by_content([new_a, new_b])

        self.assertIsNone(chosen)
        self.assertEqual(len(metrics), 2)

    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(MODULE, "_window_rect", return_value=(120, 70, 620, 300))
    @patch.object(MODULE, "_ancestor_root_handle", return_value=999)
    @patch.object(MODULE, "_window_handle_at_point", return_value=555)
    def test_locate_report_window_visually_finds_titlebar_and_resolves_handle(
        self, _handle_at_point, _ancestor, _rect, _stop
    ):
        from PIL import Image

        template = Image.open(MODULE.REPORT_WINDOW_TITLEBAR_TEMPLATE_PATH).convert(
            "RGB"
        )
        screen = Image.new("RGB", (900, 500), color=(90, 90, 90))
        screen.paste(template, (120, 70))

        handle, rect, score = MODULE._locate_report_window_visually(
            1.0, screen=screen, virtual_origin=(0, 0)
        )

        self.assertEqual(handle, 999)
        self.assertEqual(rect, (120, 70, 620, 300))
        self.assertGreater(score, 0.99)
        _ancestor.assert_called_once_with(555)

    @patch.object(MODULE, "_stop_pressed", return_value=False)
    def test_locate_report_window_visually_returns_none_when_titlebar_absent(
        self, _stop
    ):
        from PIL import Image

        screen = Image.new("RGB", (900, 500), color=(90, 90, 90))

        handle, rect, score = MODULE._locate_report_window_visually(
            0.1, screen=screen, virtual_origin=(0, 0)
        )

        self.assertIsNone(handle)
        self.assertIsNone(rect)
        self.assertLess(score, MODULE.VISUAL_MATCH_THRESHOLD)

    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(
        MODULE,
        "_locate_report_window_visually",
        return_value=(777, (0, 0, 800, 900), 0.99),
    )
    @patch.object(MODULE, "_activate_report_menu_item")
    @patch.object(MODULE, "_find_report_menu_item")
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_prefers_visual_location_when_available(
        self,
        _require_focus,
        _right_click,
        _find_menu,
        _activate,
        _locate_visually,
        _stop,
    ):
        _find_menu.return_value = ("uia", object())
        desktop_win32 = FakeDesktop([])

        result = MODULE._open_report(
            FakeMainWindow(1234),
            FakeDesktop([]),
            desktop_win32,
            MagicMock(),
            FakeMouse(),
            None,
            1.0,
        )

        self.assertEqual(result.handle, 777)
        self.assertEqual(desktop_win32.windowed_handles, [777])

    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(
        MODULE,
        "_locate_report_window_visually",
        return_value=(777, (0, 0, 800, 900), 0.99),
    )
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_opens_the_menu_with_a_right_click(
        self,
        _require_focus,
        _right_click,
        _locate_visually,
        _stop,
    ):
        # Se probo a abrir el menu con la tecla de menu contextual, para que
        # actuase sobre la fila seleccionada en vez de sobre la que hubiera
        # bajo el puntero, pero en esta aplicacion esa tecla no despliega el
        # menu ni tras devolver el foco a la lista con un clic. El clic
        # derecho si funciona de forma consistente, asi que es el que se usa.
        keyboard = MagicMock()

        MODULE._open_report(
            FakeMainWindow(1234),
            FakeDesktop([]),
            FakeDesktop([]),
            keyboard,
            FakeMouse(),
            None,
            1.0,
        )

        _right_click.assert_called_once()

    def test_report_menu_initial_is_unique_among_real_menu_items(self):
        # Escribir la inicial de un item solo es seguro si ningun otro item
        # del menu empieza por esa misma letra: si la letra fuese
        # compartida, la tecla dejaria de ejecutar el comando y pasaria a
        # rotar entre items, pudiendo dejar resaltado uno destructivo.
        # Estos son los items reales del menu contextual de Vue PACS.
        menu_items = [
            "Cargar y adjuntar informe",
            "Cargar en",
            "Cargar anonimizado",
            "Cargar imágenes clave",
            "Quick Vue",
            "Cargar serie significativa",
            "Cargar con presentación",
            "Aplicaciones externas",
            "Explorar",
            "Ver informes",
            "Crear otro informe para el estudio",
            "Adjuntar informe",
            "Firmar por lotes a Revisado",
            "Crear informe sin estudio para este paciente",
            "Menú Grabar",
            "Grabar series significativas",
            "Copiar",
            "Eliminar",
            "Envío a cliente",
            "Eliminar de caché",
            "Definir prioridad",
            "Definir estado",
            "Asignarme a mí",
            "Asignar a doctor",
            "Desbloquear estudio",
        ]
        starting_with_initial = [
            item
            for item in menu_items
            if item[0].lower() == MODULE.REPORT_MENU_INITIAL
        ]

        self.assertEqual(starting_with_initial, [MODULE.REPORT_MENU_NAME])

    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(
        MODULE,
        "_locate_report_window_visually",
        return_value=(777, (0, 0, 800, 900), 0.99),
    )
    @patch.object(MODULE, "_find_report_menu_item")
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_tries_menu_initial_before_touching_the_mouse(
        self,
        _require_focus,
        _right_click,
        _find_menu,
        _locate_visually,
        _stop,
    ):
        # La ruta de teclado no depende de coordenadas ni de que el menu
        # resalte el item por movimiento de raton, asi que se intenta
        # primero. Si funciona, no debe hacerse ningun clic sobre el menu.
        keyboard = MagicMock()
        mouse = FakeMouse()

        result = MODULE._open_report(
            FakeMainWindow(1234),
            FakeDesktop([]),
            FakeDesktop([]),
            keyboard,
            mouse,
            None,
            1.0,
        )

        self.assertEqual(result.handle, 777)
        keyboard.send_keys.assert_called_once_with(MODULE.REPORT_MENU_INITIAL)
        _find_menu.assert_not_called()
        self.assertEqual(mouse.clicks, [])
        self.assertEqual(mouse.presses, [])

    @patch.object(MODULE, "_cursor_position_and_process_id", return_value=((0, 0), 1234))
    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(MODULE, "_locate_report_window_visually", return_value=(None, None, 0.0))
    @patch.object(MODULE, "_window_rect", return_value=(0, 0, 100, 100))
    @patch.object(MODULE, "_is_real_window", return_value=True)
    @patch.object(MODULE, "_activate_report_menu_item")
    @patch.object(MODULE, "_find_report_menu_item")
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_never_sends_enter_to_the_menu(
        self,
        _require_focus,
        _right_click,
        _find_menu,
        _activate,
        _is_real_window,
        _window_rect,
        _locate_visually,
        _stop,
        _cursor_pid,
    ):
        # Sin poder confirmar que item quedo resaltado, un Enter a ciegas
        # podria activar el primer item del menu ("Cargar y adjuntar
        # informe"), que escribe en el sistema. La ruta de teclado se
        # limita a la inicial y nunca confirma con Enter.
        _find_menu.return_value = ("uia", object())
        keyboard = MagicMock()

        # Aqui no aparece ninguna ventana nueva, asi que el camino de
        # respaldo termina deteniendose de forma segura; lo que se verifica
        # es que en todo ese recorrido nunca se envio un Enter.
        with self.assertRaises(MODULE.CaptureError):
            MODULE._open_report(
                FakeMainWindow(1234),
                FakeDesktop([FakeWindowFull(handle=42)]),
                FakeDesktop([]),
                keyboard,
                FakeMouse(),
                None,
                0.2,
            )

        sent = [call.args[0] for call in keyboard.send_keys.call_args_list]
        self.assertNotIn("{ENTER}", sent)
        self.assertNotIn("~", sent)
        self.assertEqual(set(sent), {MODULE.REPORT_MENU_INITIAL})

    @patch.object(MODULE, "_cursor_position_and_process_id", return_value=((0, 0), 1234))
    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(MODULE, "_locate_report_window_visually", return_value=(None, None, 0.0))
    @patch.object(
        MODULE,
        "_window_rect",
        side_effect=lambda handle: (0, 0, 100, 100) if handle else None,
    )
    @patch.object(MODULE, "_is_real_window", side_effect=lambda handle: bool(handle))
    @patch.object(MODULE, "_activate_report_menu_item")
    @patch.object(MODULE, "_find_report_menu_item")
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_ignores_ghost_window_without_a_real_handle(
        self,
        _require_focus,
        _right_click,
        _find_menu,
        _activate,
        _is_real_window,
        _window_rect,
        _locate_visually,
        _stop,
        _cursor_pid,
    ):
        # Reproduce el caso real: aparece una ventana "nueva" transitoria
        # (probablemente un remanente del menu contextual) sin handle valido
        # ni clase, antes de que la ventana real del informe llegue a
        # existir. No debe aceptarse como si fuera la ventana del informe.
        existing = FakeWindowFull(handle=1)
        ghost = FakeWindowFull(handle=None, class_name="")
        real = FakeWindowFull(handle=5, class_name="Real")
        desktop_uia = FakeDesktopSequence(
            [[existing], [existing, ghost], [existing, ghost, real]]
        )
        _find_menu.return_value = ("uia", object())

        result = MODULE._open_report(
            FakeMainWindow(1234),
            desktop_uia,
            FakeDesktop([]),
            MagicMock(),
            FakeMouse(),
            None,
            1.0,
        )

        self.assertIs(result, real)

    @patch.object(MODULE, "_cursor_position_and_process_id", return_value=((0, 0), 1234))
    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(MODULE, "_locate_report_window_visually", return_value=(None, None, 0.0))
    @patch.object(MODULE, "_window_rect", return_value=(0, 0, 100, 100))
    @patch.object(MODULE, "_is_real_window", return_value=True)
    @patch.object(MODULE, "_foreground_window_handle")
    @patch.object(MODULE, "_focused_control_handle", return_value=None)
    @patch.object(MODULE, "_activate_report_menu_item")
    @patch.object(MODULE, "_find_report_menu_item")
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_picks_foreground_window_and_closes_the_rest(
        self,
        _require_focus,
        _right_click,
        _find_menu,
        _activate,
        _focused_control,
        _foreground_handle,
        _is_real_window,
        _window_rect,
        _locate_visually,
        _stop,
        _cursor_pid,
    ):
        existing = FakeWindowFull(handle=1)
        new_a = FakeWindowFull(handle=2)
        new_b = FakeWindowFull(handle=3)
        desktop_uia = FakeDesktopSequence([[existing], [existing, new_a, new_b]])
        _find_menu.return_value = ("uia", object())
        _foreground_handle.return_value = 3

        result = MODULE._open_report(
            FakeMainWindow(1234),
            desktop_uia,
            FakeDesktop([]),
            MagicMock(),
            FakeMouse(),
            None,
            1.0,
        )

        self.assertIs(result, new_b)
        self.assertTrue(new_a.closed)
        self.assertFalse(new_b.closed)

    @patch.object(MODULE, "_cursor_position_and_process_id", return_value=((0, 0), 1234))
    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(MODULE, "_locate_report_window_visually", return_value=(None, None, 0.0))
    @patch.object(MODULE, "_window_rect", return_value=(0, 0, 100, 100))
    @patch.object(MODULE, "_is_real_window", return_value=True)
    @patch.object(MODULE, "_foreground_window_handle")
    @patch.object(MODULE, "_focused_control_handle")
    @patch.object(MODULE, "_activate_report_menu_item")
    @patch.object(MODULE, "_find_report_menu_item")
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_picks_window_containing_focused_control(
        self,
        _require_focus,
        _right_click,
        _find_menu,
        _activate,
        _focused_control,
        _foreground_handle,
        _is_real_window,
        _window_rect,
        _locate_visually,
        _stop,
        _cursor_pid,
    ):
        # Reproduce el caso real: GetForegroundWindow() sigue devolviendo el
        # marco principal MDI (no coincide con ninguna ventana nueva), pero
        # GetGUIThreadInfo reporta un control con foco que SI esta dentro de
        # una de las ventanas nuevas (relacion detectada via IsChild, aqui
        # simulada con MODULE._window_contains_handle parcheado).
        existing = FakeWindowFull(handle=1)
        new_a = FakeWindowFull(handle=2, class_name="Alfa")
        new_b = FakeWindowFull(handle=3, class_name="Beta")
        desktop_uia = FakeDesktopSequence([[existing], [existing, new_a, new_b]])
        _find_menu.return_value = ("uia", object())
        _foreground_handle.return_value = 1  # el marco principal, no nuevo
        _focused_control.return_value = 30  # control hijo dentro de new_b

        with patch.object(
            MODULE,
            "_window_contains_handle",
            side_effect=lambda window_handle, target: window_handle == 3
            and target == 30,
        ):
            result = MODULE._open_report(
                FakeMainWindow(1234),
                desktop_uia,
                FakeDesktop([]),
                MagicMock(),
                FakeMouse(),
                None,
                1.0,
            )

        self.assertIs(result, new_b)
        self.assertTrue(new_a.closed)
        self.assertFalse(new_b.closed)

    @patch.object(MODULE, "_cursor_position_and_process_id", return_value=((0, 0), 1234))
    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(MODULE, "_locate_report_window_visually", return_value=(None, None, 0.0))
    @patch.object(MODULE, "_window_rect", return_value=(0, 0, 100, 100))
    @patch.object(MODULE, "_is_real_window", return_value=True)
    @patch.object(MODULE, "_select_report_window_by_content")
    @patch.object(MODULE, "_foreground_window_handle")
    @patch.object(MODULE, "_focused_control_handle", return_value=None)
    @patch.object(MODULE, "_activate_report_menu_item")
    @patch.object(MODULE, "_find_report_menu_item")
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_falls_back_to_content_when_no_window_matches_focus(
        self,
        _require_focus,
        _right_click,
        _find_menu,
        _activate,
        _focused_control,
        _foreground_handle,
        _select_by_content,
        _is_real_window,
        _window_rect,
        _locate_visually,
        _stop,
        _cursor_pid,
    ):
        # Ni el primer plano ni el foco distinguen (misma clase generica en
        # todas las ventanas de esta plantilla); se usa como ultimo recurso
        # la cantidad de texto (solo longitud, nunca contenido) de cada
        # ventana nueva.
        existing = FakeWindowFull(handle=1)
        new_a = FakeWindowFull(handle=2, class_name="Alfa")
        new_b = FakeWindowFull(handle=3, class_name="Beta")
        desktop_uia = FakeDesktopSequence([[existing], [existing, new_a, new_b]])
        _find_menu.return_value = ("uia", object())
        _foreground_handle.return_value = 999
        _select_by_content.return_value = (
            new_b,
            [(new_a, 400, 0, 0), (new_b, 90000, 1800, 12)],
        )

        result = MODULE._open_report(
            FakeMainWindow(1234),
            desktop_uia,
            FakeDesktop([]),
            MagicMock(),
            FakeMouse(),
            None,
            1.0,
        )

        self.assertIs(result, new_b)
        self.assertTrue(new_a.closed)
        self.assertFalse(new_b.closed)

    @patch.object(MODULE, "_cursor_position_and_process_id", return_value=((0, 0), 1234))
    @patch.object(MODULE, "_stop_pressed", return_value=False)
    @patch.object(MODULE, "_locate_report_window_visually", return_value=(None, None, 0.0))
    @patch.object(MODULE, "_window_rect", return_value=(0, 0, 100, 100))
    @patch.object(MODULE, "_is_real_window", return_value=True)
    @patch.object(MODULE, "_select_report_window_by_content", return_value=(None, []))
    @patch.object(MODULE, "_focused_control_class_name", return_value="?")
    @patch.object(MODULE, "_foreground_window_class_name", return_value="MDIClient")
    @patch.object(MODULE, "_foreground_window_handle")
    @patch.object(MODULE, "_focused_control_handle", return_value=None)
    @patch.object(MODULE, "_activate_report_menu_item")
    @patch.object(MODULE, "_find_report_menu_item")
    @patch.object(MODULE, "_right_click_vue_at_cursor")
    @patch.object(MODULE, "_require_vue_focus")
    def test_open_report_stops_when_no_window_matches_foreground(
        self,
        _require_focus,
        _right_click,
        _find_menu,
        _activate,
        _focused_control,
        _foreground_handle,
        _foreground_class,
        _focused_class,
        _select_by_content,
        _is_real_window,
        _window_rect,
        _locate_visually,
        _stop,
        _cursor_pid,
    ):
        existing = FakeWindowFull(handle=1)
        new_a = FakeWindowFull(handle=2, class_name="Alfa")
        new_b = FakeWindowFull(handle=3, class_name="Beta")
        desktop_uia = FakeDesktopSequence([[existing], [existing, new_a, new_b]])
        _find_menu.return_value = ("uia", object())
        _foreground_handle.return_value = 999

        with self.assertRaisesRegex(MODULE.CaptureError, "Alfa, Beta.*MDIClient.*\\?"):
            MODULE._open_report(
                FakeMainWindow(1234),
                desktop_uia,
                FakeDesktop([]),
                MagicMock(),
                FakeMouse(),
                None,
                1.0,
            )

        self.assertFalse(new_a.closed)
        self.assertFalse(new_b.closed)

    def test_win32_menu_activation_preserves_command_selection(self):
        report_item = FakeItem()

        MODULE._activate_report_menu_item("win32", report_item)

        self.assertTrue(report_item.selected)
        self.assertFalse(report_item.invoked)

    @patch.object(MODULE, "_activate_report_menu_item")
    @patch.object(MODULE, "_find_report_menu_item")
    def test_copy_report_content_via_context_menu_selects_then_copies(
        self, _find_menu, _activate
    ):
        # El panel de contenido del informe es un control personalizado
        # que solo copia via su propio menu contextual: clic derecho,
        # "Seleccionar todo", clic derecho de nuevo, "Copiar".
        select_all_item = ("uia", FakeItem(text=MODULE.SELECT_ALL_MENU_NAME))
        copy_item = ("uia", FakeItem(text=MODULE.COPY_MENU_NAME))
        _find_menu.side_effect = [select_all_item, copy_item]
        mouse = FakeMouse()

        MODULE._copy_report_content_via_context_menu(
            mouse,
            FakeDesktop([]),
            FakeDesktop([]),
            (100, 200),
            1234,
            None,
            5.0,
        )

        self.assertEqual(
            mouse.clicks,
            [
                {"button": "right", "coords": (100, 200)},
                {"button": "right", "coords": (100, 200)},
            ],
        )
        target_names = [call.kwargs["target_name"] for call in _find_menu.call_args_list]
        self.assertEqual(
            target_names, [MODULE.SELECT_ALL_MENU_NAME, MODULE.COPY_MENU_NAME]
        )
        self.assertEqual(_activate.call_count, 2)

    @patch.object(MODULE, "_find_report_menu_item", return_value=None)
    def test_copy_report_content_via_context_menu_raises_when_item_missing(
        self, _find_menu
    ):
        mouse = FakeMouse()

        with self.assertRaisesRegex(MODULE.CaptureError, MODULE.SELECT_ALL_MENU_NAME):
            MODULE._copy_report_content_via_context_menu(
                mouse,
                FakeDesktop([]),
                FakeDesktop([]),
                (100, 200),
                1234,
                None,
                5.0,
            )

    def test_activate_report_menu_item_prefers_a_real_click_when_possible(self):
        # Algunos menus contextuales dibujados a mano no ejecutan el
        # comando real cuando se activan solo por UI Automation. Si hay
        # mouse disponible y el item expone su posicion en pantalla, se
        # hace clic real ahi en vez de usar invoke()/select().
        report_item = FakeItem(rect=FakeRect(120, 340))
        mouse = FakeMouse()

        MODULE._activate_report_menu_item("uia", report_item, mouse=mouse)

        # El clic se emite como entrada-desde-un-punto-vecino + pulsar +
        # soltar, no como un click() instantaneo: un menu owner-drawn solo
        # activa el item que quedo resaltado por un movimiento real.
        self.assertEqual(
            mouse.moves, [{"coords": (108, 340)}, {"coords": (120, 340)}]
        )
        self.assertEqual(
            mouse.presses, [{"button": "left", "coords": (120, 340)}]
        )
        self.assertEqual(
            mouse.releases, [{"button": "left", "coords": (120, 340)}]
        )
        self.assertFalse(report_item.invoked)
        self.assertFalse(report_item.selected)

    def test_activate_report_menu_item_falls_back_when_rectangle_unavailable(self):
        report_item = FakeItem()  # sin rectangulo
        mouse = FakeMouse()

        MODULE._activate_report_menu_item("uia", report_item, mouse=mouse)

        self.assertEqual(mouse.clicks, [])
        self.assertTrue(report_item.invoked)

    def test_age_phrase_generalizes_advanced_age(self):
        self.assertEqual(MODULE.age_phrase("Edad: 92Y 3M"), "Paciente de 90 años o más.")

    def test_age_phrase_keeps_exact_value_below_threshold(self):
        self.assertEqual(MODULE.age_phrase("Edad: 45A"), "Paciente de 45 años.")

    def test_age_phrase_empty_when_field_absent(self):
        self.assertEqual(MODULE.age_phrase("Sin campo de edad aca."), "")

    def test_anonymize_generalizes_inline_age_shorthand(self):
        clean = MODULE.anonymize("Paciente 92 a con sindrome confusional, no responde.")

        self.assertNotIn("92", clean)
        self.assertIn("90 a con sindrome confusional", clean)

    def test_anonymize_generalizes_inline_age_with_anos(self):
        clean = MODULE.anonymize("Paciente de 95 años de edad, traida por familiares.")

        self.assertNotIn("95", clean)
        self.assertIn("90 años de edad", clean)

    def test_anonymize_keeps_age_below_threshold_and_numeric_ranges(self):
        clean = MODULE.anonymize(
            "Paciente de 45 años. Coleccion de 6 a 8 mm en polo inferior."
        )

        self.assertIn("45 años", clean)
        self.assertIn("6 a 8 mm", clean)

    def test_detect_region_recognizes_cranial_studies_as_cabeza_cuello(self):
        self.assertEqual(MODULE.detect_region("TC de craneo sin contraste."), "cabeza_cuello")
        self.assertEqual(MODULE.detect_region("RM cerebral con contraste."), "cabeza_cuello")

    def test_detect_region_recognizes_temporomandibular_joint_studies(self):
        # La ATM es articulacion propia y con protocolo propio: no debe
        # caer en cabeza_cuello (craneoencefalico) ni quedar sin clasificar.
        self.assertEqual(
            MODULE.detect_region("RM articulaciones temporomandibulares"), "atm"
        )
        self.assertEqual(MODULE.detect_region("RM ATM bilateral"), "atm")
        self.assertEqual(
            MODULE.detect_region("Resonancia magnetica temporo-mandibular"), "atm"
        )
        # No debe robarle estudios craneoencefalicos a cabeza_cuello.
        self.assertEqual(MODULE.detect_region("RM craneo"), "cabeza_cuello")

    def test_parse_report_prepends_generalized_age_and_drops_rest_of_header(self):
        header = (
            "Nombre: Paciente Ficticio\n"
            "Fecha de Nacimiento: 01/01/1934 Edad: 92Y 1M\n"
            "NHC: 9999999\n\n"
        )
        parsed = MODULE.parse_report(header + REPORT)

        self.assertTrue(parsed["clinical_data"].startswith("Paciente de 90 años o más."))
        self.assertNotIn("1934", parsed["clinical_data"])
        self.assertNotIn("Paciente Ficticio", parsed["clinical_data"])
        self.assertNotIn("9999999", parsed["clinical_data"])

    def test_parse_report_keeps_exact_age_below_threshold(self):
        header = "Fecha de Nacimiento: 01/01/1980 Edad: 45A\n\n"
        parsed = MODULE.parse_report(header + REPORT)

        self.assertTrue(parsed["clinical_data"].startswith("Paciente de 45 años."))

    def test_parse_report_uses_inner_exploration_and_removes_signature(self):
        parsed = MODULE.parse_report(REPORT)

        self.assertEqual(parsed["exploration"], "RM de rodilla.")
        self.assertNotIn("Nombre Apellido", parsed["impression"])
        self.assertEqual(parsed["impression"], "Sin hallazgos patológicos significativos.")

    def test_candidate_masks_impression_from_raw_input(self):
        candidate = MODULE.build_review_candidate(MODULE.parse_report(REPORT))

        self.assertNotIn("Impresion diagnostica", candidate["raw_input"])
        self.assertIn("Impresion diagnostica", candidate["final_report"])
        self.assertEqual(candidate["region"], "rodilla")
        self.assertEqual(candidate["modality"], "RM")
        self.assertEqual(candidate["approval_status"], "candidate")
        self.assertFalse(candidate["sft_eligible"])

    def test_anonymize_rejects_identifier_fields_and_redacts_dates(self):
        clean = MODULE.anonymize(
            "NHC: 123456789\nHallazgo estable desde 20/07/2026.\nDr: Nombre Apellido"
        )

        self.assertNotIn("123456789", clean)
        self.assertNotIn("Nombre Apellido", clean)
        self.assertIn("[FECHA]", clean)

    def test_missing_impression_is_kept_with_empty_field(self):
        parsed = MODULE.parse_report(REPORT_NO_IMPRESSION)

        self.assertEqual(parsed["impression"], "")
        self.assertNotIn("Nombre Ficticio", parsed["findings"])

        candidate = MODULE.build_review_candidate(parsed)

        self.assertEqual(candidate["approval_status"], "candidate")
        self.assertFalse(candidate["sft_eligible"])
        self.assertIn("Impresion diagnostica", candidate["final_report"])

    def test_missing_findings_is_rejected(self):
        with self.assertRaises(MODULE.CaptureError):
            MODULE.parse_report(REPORT.replace("Hallazgos:", "Resultado:"))

    def test_candidate_section_labels_exposes_only_labels_not_values(self):
        labels = MODULE.candidate_section_labels(REPORT)

        self.assertIn("Origen", labels)
        self.assertIn("Descripción", labels)
        self.assertIn("Datos clínicos", labels)
        self.assertIn("Hallazgos", labels)
        self.assertIn("Impresión diagnóstica", labels)
        self.assertIn("Dr", labels)
        for label in labels:
            self.assertNotIn("Nombre Apellido", label)
            self.assertNotIn("dolor mecánico", label)
            self.assertNotIn("21/07/2026", label)

    def test_candidate_section_labels_deduplicates_and_skips_non_header_lines(self):
        text = "Técnica: TC helicoidal\nTécnica: repetido\nSin dos puntos aca\nOtra: si"

        labels = MODULE.candidate_section_labels(text)

        self.assertEqual(labels, ["Técnica", "Otra"])

    def test_missing_clinical_data_is_rejected(self):
        with self.assertRaises(MODULE.CaptureError):
            MODULE.parse_report(REPORT.replace("Datos clínicos:", "Antecedentes:"))

    def test_parse_report_falls_back_to_top_exploration_and_conclusion_alias(self):
        parsed = MODULE.parse_report(REPORT_NO_BODY_EXPLORATION_WITH_CONCLUSION)

        self.assertIn("TC ABDOMEN Y PELVIS SIN CONTRASTE", parsed["exploration"])
        self.assertIn("dolor abdominal difuso", parsed["clinical_data"])
        self.assertIn("Hígado, bazo y páncreas", parsed["findings"])
        self.assertEqual(
            parsed["impression"], "Estudio abdominal sin hallazgos agudos."
        )
        self.assertNotIn("Nombre Ficticio3", parsed["impression"])

        candidate = MODULE.build_review_candidate(parsed)
        self.assertEqual(candidate["modality"], "TC")
        self.assertEqual(candidate["region"], "abdomen_pelvis")

    def test_parse_report_accepts_headers_without_colon(self):
        parsed = MODULE.parse_report(REPORT_HEADERS_WITHOUT_COLON)

        self.assertEqual(parsed["exploration"], "TC craneal sin contraste.")
        self.assertIn("cefalea", parsed["clinical_data"])
        self.assertIn("Sin alteraciones agudas", parsed["findings"])
        self.assertIn("sin hallazgos agudos", parsed["impression"])
        self.assertNotIn("Nombre Ficticio2", parsed["impression"])

    def test_atomic_append_deduplicates(self):
        candidate = MODULE.build_review_candidate(MODULE.parse_report(REPORT))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pending.jsonl"
            first = MODULE.append_candidate(output, candidate)
            second = MODULE.append_candidate(output, candidate)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(rows), 1)

    def test_capture_limit_is_enforced_before_automation_starts(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--capture", "--confirm-read-only", "--max-cases", "501"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("entre 1 y 500", result.stderr)

    def test_visual_capture_allows_up_to_five_hundred_cases(self):
        # Lo que valida este test es que --max-cases 500 no se rechaza de
        # entrada con ningun mensaje de limite de los topes anteriores (1,
        # 5 o 50). Se usa un patron de titulo que nunca puede coincidir con
        # nada real, para que _find_main_window falle rapido y el test no
        # dependa de si hay o no una ventana de Vue PACS abierta de verdad
        # en el equipo donde corre la suite (y no toque la automatizacion
        # real ni el raton).
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--capture",
                "--confirm-read-only",
                "--max-cases",
                "500",
                "--window-title-pattern",
                "esta-ventana-de-prueba-nunca-existe-de-verdad",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotIn("limitada a un caso", result.stderr)
        self.assertNotIn("entre 1 y 5", result.stderr)
        self.assertNotIn("entre 1 y 50", result.stderr)
        self.assertNotIn("entre 1 y 500", result.stderr)


class KeepSystemAwakeTests(unittest.TestCase):
    def test_prevents_sleep_on_enter_and_releases_on_exit(self):
        calls = []
        fake_kernel32 = MagicMock()
        fake_kernel32.SetThreadExecutionState.side_effect = (
            lambda flags: calls.append(flags)
        )
        with patch.object(MODULE.ctypes, "windll") as fake_windll:
            fake_windll.kernel32 = fake_kernel32
            with MODULE._keep_system_awake():
                pass

        self.assertEqual(
            calls,
            [
                MODULE._ES_CONTINUOUS
                | MODULE._ES_SYSTEM_REQUIRED
                | MODULE._ES_DISPLAY_REQUIRED,
                MODULE._ES_CONTINUOUS,
            ],
        )

    def test_releases_even_when_body_raises(self):
        calls = []
        fake_kernel32 = MagicMock()
        fake_kernel32.SetThreadExecutionState.side_effect = (
            lambda flags: calls.append(flags)
        )
        with patch.object(MODULE.ctypes, "windll") as fake_windll:
            fake_windll.kernel32 = fake_kernel32
            with self.assertRaises(RuntimeError):
                with MODULE._keep_system_awake():
                    raise RuntimeError("boom")

        self.assertEqual(calls[-1], MODULE._ES_CONTINUOUS)


if __name__ == "__main__":
    unittest.main()
