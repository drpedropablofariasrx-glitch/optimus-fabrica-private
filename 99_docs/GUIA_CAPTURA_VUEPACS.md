# Captura supervisada de informes de Vue PACS

## Alcance

Este prototipo copia informes finales ya visibles en Vue PACS y crea candidatos
anonimizados para revisión. No firma, modifica, adjunta ni elimina informes. No
se conecta a OpenAI, DeepSeek ni a ningún servicio externo.

Antes de utilizarlo debe existir autorización del hospital para extraer y usar
los informes con esta finalidad.

## Instalación opcional

La aplicación principal de OPTIMUS no necesita esta dependencia. Para habilitar
solo el capturador:

```powershell
python -m pip install -r requirements-vuepacs.txt
```

## Prueba 1: procesar manualmente un informe copiado

En Vue PACS abre `Ver informes`, utiliza `Seleccionar todo` y `Copiar`, y ejecuta:

```powershell
python scripts\capturar_vuepacs.py --parse-clipboard
```

El portapapeles se vacía al terminar. El candidato se guarda en:

```text
datasets/private/vuepacs_import/pendientes_revision.jsonl
```

## Prueba 2: comprobar los controles sin abrir informes

Selecciona una fila en la lista de trabajo y ejecuta:

```powershell
python scripts\capturar_vuepacs.py --probe
```

Durante la cuenta atrás de cinco segundos, vuelve a Vue PACS, selecciona una
fila y deja el puntero encima de esa misma fila. No regreses a PowerShell hasta
que la sonda termine. La sonda abre el menú con un clic derecho supervisado y
se detiene si el puntero no está sobre Vue PACS.

El modo `probe` abre el menú contextual, busca exactamente `Ver informes`
primero mediante UI Automation y después mediante el menú nativo Win32. Lo
cierra sin invocarlo. Si no lo encuentra, muestra solamente recuentos técnicos
de controles y ventanas emergentes; no imprime contenido del informe.
Cuando Vue PACS no publica controles accesibles, la sonda compara en memoria
dos plantillas anonimizadas que contienen solo el icono o el texto
`Ver informes`. Esto cubre el menú normal y el menú pegado al borde de la
pantalla. No guarda ninguna captura de la pantalla.

## Prueba 3: captura supervisada

Empieza con un solo informe. Selecciona la fila, deja el puntero encima de ella
y ejecuta:

```powershell
python scripts\capturar_vuepacs.py --capture --confirm-read-only --max-cases 1
```

Mantén pulsado `F12` para detener el recorrido. Tras comprobar el resultado en
OPTIMUS, se pueden procesar tandas de hasta cinco informes:

```powershell
python scripts\capturar_vuepacs.py --capture --confirm-read-only --max-cases 5
```

Al pasar a la siguiente fila, el capturador mueve el puntero a la fila que ha
quedado seleccionada. Esto evita que el menú contextual vuelva a abrir el
informe anterior. Si un informe no tiene el formato esperado, se registra como
omitido y la tanda continúa; un fallo de foco, ventana o seguridad sí detiene
la captura.

## Integración con Fábrica

Cada candidato válido se añade, con `origen = vuepacs`, a la cola privada:

```text
datasets/private/vuepacs_import/pendientes_revision.jsonl
```

En Fábrica abre **Revisar SFT**, selecciona **Origen: VuePACS** y revisa cada
candidato. Solo una aprobación manual puede incorporarlo al corpus de
entrenamiento; la captura no modifica prompts, reglas, casos Gold ni el modelo.
Los duplicados se detectan por una huella del contenido anonimizado.

## Controles de seguridad

- Solo invoca un elemento de menú cuyo nombre sea exactamente `Ver informes`.
- El respaldo Win32 usa el identificador interno del elemento, no coordenadas.
- Exige que el informe se abra en una ventana nueva antes de cerrarla.
- Si copia la lista de pacientes en vez de un informe, el parser la rechaza.
- Vacía el portapapeles después de cada intento.
- Elimina campos de identidad, firma, fechas, teléfonos y números largos.
- Ningún caso se marca automáticamente como aprobado o apto para SFT.
- Evita duplicados mediante una huella del contenido anonimizado.
- Los informes sin sección de Impresión diagnóstica no se descartan: se
  guardan con ese campo vacío, útiles para la tarea Hallazgos → Impresión.
- Del encabezado de identificación (nombre, NHC, episodio, hospital, médico
  solicitante...) solo se conserva la edad, como frase clínica corta. A
  partir de 90 años se generaliza a "90 años o más" para no facilitar la
  reidentificación de pacientes muy longevos.

No debe ampliarse el límite hasta revisar manualmente los cinco primeros casos.
