# Estado del proyecto — IA local en radiología MSK/abdominal
**Para presentar al proyecto Optimus — julio 2026**

---

## 1. Objetivo del proyecto

Construir un sistema que genere informes radiológicos estructurados y, a la vez, acumule un dataset limpio con el que entrenar en el futuro un modelo local (Qwen3:8b vía QLoRA), sin depender permanentemente de un proveedor de IA en la nube.

**Principio rector, validado en la práctica:** *"Lo que se hace más inteligente es el sistema, no el modelo."* El activo valioso no es GPT-4o ni Claude — son las reglas clínicas destiladas, el validador determinista y el dataset de casos corregidos. El modelo de IA es una pieza intercambiable.

---

## 2. Lo que existe hoy, funcionando

### 2.1 La fábrica (`fabrica_abdomen.py`)
Programa Python local (Flask), corre en el ordenador personal, con interfaz web tipo ChatGPT. Es el sistema de referencia, probado y en uso real:

- **Generación:** llama a un proveedor de IA (OpenAI / Claude / DeepSeek, seleccionables) con un `SYSTEM_PROMPT` fijo que contiene las reglas de la región.
- **Validador determinista:** código Python (no IA) que revisa el informe generado contra reglas duras — umbrales de UH (esteatosis, lipoma, lipomatosis pancreática), mm (aorta), coherencia de realce por fases, formato. Señala incoherencias; nunca corrige solo.
- **Captura de correcciones:** guarda siempre el informe de la IA *y* la versión que el radiólogo corrige, más una nota. De ahí sale una **bandeja de reglas candidatas**: un modelo analiza la diferencia y propone si es una regla generalizable o un cambio puntual; el radiólogo aprueba o descarta. El sistema nunca cambia sus propias reglas sin confirmación humana.
- **Chat de sistema:** permite pedir cambios de prompt/reglas en lenguaje natural. Antes de aplicar, muestra el *diff* exacto; guarda copia de seguridad automática; permite deshacer.
- **Persistencia local:** cada caso se guarda en disco (`.md` legible + `.json` estructurado) y se acumula en `abdomen_dataset.jsonl`, el material para el futuro fine-tuning.
- **Puente hospital → casa:** como el trabajo clínico ocurre en dos ordenadores distintos, existe un formato de captura de texto (`### CASO ### [BRUTO] [INFORME] [MEJORAS] [NOTAS] ### FIN ###`) y un importador que trocea y carga varios casos de golpe.

### 2.2 Extracción de reglas desde el histórico
Método probado sobre un corpus real de ~237 casos de TC abdomen-pelvis (un año de trabajo en ChatGPT):

- **Reglas explícitas** — las que el radiólogo dictó literalmente ("recuerda que...", "guarda esto").
- **Reglas implícitas** — las que emergen de una corrección sin instrucción explícita (detectadas por lectura con criterio, no por regex: la detección automática generaba ~95% de ruido).

Resultado: **31 reglas consolidadas** (12 duras → validador; 19 blandas → prompt), cada una con cita textual y línea de origen, documentadas en `REGLAS_ABDOMEN_MAESTRAS.md`. Este método es el que hay que replicar para cada nueva región (rodilla, lumbar, cervical), a partir de los hilos históricos ya existentes en ChatGPT — **no** redactando resúmenes desde los libros de texto.

---

## 3. Decisiones de arquitectura, ya tomadas y validadas

| Decisión | Resultado |
|---|---|
| Builder (nube) vs. Local (Ollama) | Fases secuenciales, no paralelas. La API en la nube produce el dataset limpio; el modelo local es el destino cuando haya suficiente dataset. |
| RAG | **Aplazado a propósito.** Las reglas destiladas en el prompt superan al RAG sobre PDFs a esta escala. Se reconsiderará solo si aparecen casos raros que las reglas no cubran. |
| PDFs de bibliografía | Nunca en producción directa. Solo como fuente para, si hiciera falta, destilar reglas — y solo desde libros de posesión legítima propia, nunca de contenido con licencia de terceros. |
| Multi-región | Una única fábrica parametrizable (selector de región + prompt/reglas propias por región), no un proyecto distinto por cada zona anatómica. |
| Persistencia | Archivos locales + `.jsonl`, sin base de datos ni vectores todavía. Se añadirá SQLite solo si el volumen de consultas lo justifica. |
| Respaldo | Carpeta del proyecto dentro de Google Drive (respaldo pasivo) + Git (versionado de reglas y código). Pendiente resolver anonimización antes de que datos reales salgan del equipo. |
| Proveedores de IA | OpenAI/Claude ya integrados; DeepSeek disponible; NVIDIA NIM (catálogo gratuito de modelos open-weight, API compatible con OpenAI) identificado como vía barata para *probar* qué modelo open-weight rendiría bien en local, no para sustituir la fase de construcción de dataset de alta calidad. |

---

## 4. Camino hacia el modelo local (cuándo y cómo)

1. **Fase actual — fábrica en la nube:** produce dataset limpio por región.
2. **Umbral de disparo:** ~100 casos gold validados por región.
3. **QLoRA sobre Qwen3:8b** (hardware: RTX 5060, 8 GB VRAM — ajustado pero viable en 4-bit; puede requerir GPU cloud puntual para el entrenamiento si la VRAM no alcanza con la longitud de secuencia necesaria).
4. **Modelo local + RAG ligero** para conocimiento bibliográfico puntual — el fine-tuning aporta *comportamiento* (formato, estilo, contención diagnóstica); el RAG aporta *datos* frescos cuando haga falta.
5. **Criterio de paso a producción local:** el modelo local debe igualar al builder en un set de test de ~20 casos fijos antes de sustituirlo.

**Importante:** ningún modelo local pequeño va a igualar el razonamiento clínico fino de GPT-4o/Claude en esta fase. El fine-tuning enseña *comportamiento consistente*, no *inteligencia nueva*. Esto hay que comunicarlo con expectativas realistas.

---

## 5. Frentes abiertos ahora mismo (por orden de prioridad real)

1. **Bug D8 del validador** — falso positivo: la regla de esteatosis no distingue negaciones ("no debe afirmarse esteatosis") de afirmaciones reales. Corrección de código pendiente, no de prompt.
2. **Generalización multi-región** — dar a la fábrica un selector de región (abdomen/rodilla/lumbar/cervical) para que cada una cargue su propio prompt y reglas duras.
3. **Extracción de reglas de lumbar y cervical** — aplicar el mismo método de extracción (documentado en el punto 2.2) sobre los hilos históricos de ChatGPT de esas regiones, que son las de mayor volumen diario.
4. **Flujo de solicitudes escaneadas del hospital de Xàtiva (worklist)** — **en pausa por motivo de privacidad**: requiere procesar PDFs con datos identificables de pacientes reales. Mientras la autorización institucional para usar proveedores de IA en la nube esté pendiente de firma, cualquier desarrollo debe hacerse con **OCR local (Tesseract) y datos de prueba ficticios**, nunca con solicitudes reales ni en servicios externos.

---

## 6. Lecciones de proceso, útiles para Optimus

- **Cerrar antes de abrir:** la tentación constante (propia y de otras herramientas de IA consultadas en el camino) es ampliar el alcance — ontologías, motores de consenso multi-modelo, arquitecturas de plugins — antes de cerrar lo que ya está en marcha. La disciplina de terminar un frente antes de abrir el siguiente ha sido determinante para tener algo *funcionando* en vez de solo *diseñado*.
- **El validador determinista es la pieza de mayor retorno:** cualquier regla comprobable por cifras o formato debe ir a código, nunca depender de que un modelo "se acuerde" de aplicarla.
- **Humano en el bucle, siempre:** ninguna regla se aplica, y ningún cambio de prompt se guarda, sin mostrar antes el efecto exacto (diff) y sin posibilidad de deshacer.
- **Privacidad como límite de diseño, no como ajuste posterior:** cualquier función que toque datos identificables de pacientes se contiene a local y a autorización explícita antes de construirse, no después.
