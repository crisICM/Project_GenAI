# Deliverable 2 — Extracción de solicitudes de emergencia

Este sistema transforma mensajes informales de emergencia en español en un objeto JSON que contiene los suministros todavía solicitados, sus cantidades y unidades, el destino vigente de entrega, las referencias para reconocer el lugar y un nivel de urgencia del 1 al 5. La inferencia se ejecuta localmente mediante Ollama.

La demostración compara una versión base con instrucciones simples (`Run_AI_D1.py`) y la solución del Deliverable 2 con instrucciones estructuradas y ejemplos (`Run_AI_D2.py`). Ambos programas interactivos utilizan **`ministral-3:3b`**.

Las instrucciones buscan reducir errores al interpretar actualizaciones, distinguir ofrecimientos de solicitudes y extraer cantidades, referencias y urgencia.

## Archivos importantes

| Archivo o carpeta | Función |
| --- | --- |
| `Run_AI_D1.py` | Versión base interactiva, con el prompt de sistema incluido en el código. |
| `Run_AI_D2.py` | Solución interactiva que carga las instrucciones desde `Instruction_2.txt`. |
| `Instruction_2.txt` | Reglas de extracción, rúbrica de urgencia y ejemplos completos. |
| `Run_Prompts.py` | Ejecuta la solución sobre todos los archivos de prueba y guarda las respuestas y los datos de ejecución. |
| `Prompts_Separados/` | Los 21 mensajes individuales utilizados por el programa de pruebas. |
| `Prompts_deposito.txt` | Mensajes reunidos para consultarlos o copiarlos. No es el archivo de entrada del programa de pruebas. |
| `Rubrica.txt` | Respuestas de referencia y comentarios para evaluar manualmente. |
| `Outputs_D2/` | Ejecuciones previamente guardadas de Qwen, Ministral y Gemma. |
| `MODELS_AI` | Notas sobre los modelos. La configuración utilizada está definida en los programas Python. |

## Instalación

Instala Python, Git y [Ollama](https://ollama.com/download).

La grabación utiliza Windows, VS Code y Python 3.14.7. VS Code es opcional: los programas también se ejecutan desde una terminal.

Debes disponer de suficiente memoria RAM/VRAM y espacio en disco para el modelo descargado. Esta ejecución local no requiere una clave de API pagada.

### 1. Clonar el repositorio

```bash
git clone https://github.com/crisICM/Project_GenAI.git
cd Project_GenAI/Deliverable_2
```

### 2. Crear un entorno virtual

```bash
python -m venv .venv
```

### 3. Activar el entorno virtual

Utiliza el comando correspondiente a tu terminal.

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

**Símbolo del sistema de Windows (CMD):**

```bat
.venv\Scripts\activate.bat
```

**Linux/macOS:**

```bash
source .venv/bin/activate
```

Si tu sistema utiliza el comando `python3`, crea el entorno con:

```bash
python3 -m venv .venv
```

Después de activarlo, utiliza `python` para los comandos restantes.

### 4. Instalar la dependencia de Python

```bash
python -m pip install ollama
```

Los demás módulos importados pertenecen a la biblioteca estándar de Python.

### 5. Iniciar Ollama y descargar el modelo

Mantén abierta la aplicación Ollama. Si el servidor todavía no está funcionando, ejecuta lo siguiente en otra terminal y déjala abierta:

```bash
ollama serve
```

Descarga el modelo utilizado en la demostración:

```bash
ollama pull ministral-3:3b
```

Comprueba que esté disponible:

```bash
ollama list
```

## Reproducir la comparación del video

Ejecuta los siguientes comandos **desde la carpeta `Deliverable_2`**. La solución interactiva busca `Instruction_2.txt` en el directorio de trabajo actual.

### 1. Ejecutar la versión base

```bash
python Run_AI_D1.py
```

Cuando aparezca `You:`, pega el siguiente mensaje en **una sola línea** y presiona Enter.

Corresponde a la prueba 06 de `Prompts_Separados/` y es el mensaje utilizado en la grabación:

```text
Impecable la gestión municipal, un aplauso por las cero frazadas y las cero linternas que prometieron mandar anoche a Dichato, se nos inundó hasta el techo y todavía estamos alumbrándonos con la pantalla del celular. En la casa del portón verde somos 9 damnificados: 4 lograron rescatar su ropa de cama, así que calculen cuántos quedamos durmiendo en el suelo húmedo. Si el camión municipal llega antes de que oscurezca traigan solo las frazadas que faltan, pero si llegan tarde sumen linternas con pilas porque la matriz de la cancha explotó y no hay luz en toda la cuadra.
```

Espera a que aparezcan `ANSWER:` y el JSON generado. Escribe `exit` para cerrar la sesión.

### 2. Ejecutar la solución del Deliverable 2

```bash
python Run_AI_D2.py
```

Pega **el mismo mensaje**, espera el JSON y escribe `exit`.

Ambos programas muestran las respuestas en la terminal y no las guardan automáticamente. Conservan el historial de conversación hasta que se cierran.

Para probar otro mensaje independiente, reinicia el programa.

### Qué muestra la grabación

La versión base devuelve frazadas y linternas con cantidades desconocidas, `Dichato` como destino, ninguna referencia y urgencia 5.

La solución devuelve una cantidad de 5 frazadas, pero también utiliza incorrectamente `Revisión Manual` como recurso y `linternas` como unidad, y reemplaza el destino por `Revisión Manual`.

Este ejemplo muestra una mejora en la cantidad extraída y un fallo que persiste al interpretar solicitudes condicionales y extraer la ubicación. La respuesta de la solución no es completamente correcta.

Al revisarla, comprueba si conserva la ubicación conocida y la referencia al portón verde, representa correctamente la solicitud de linternas y justifica la urgencia según la rúbrica de `Instruction_2.txt`.

Las respuestas exactas pueden variar: los programas interactivos no fijan una semilla y sus parámetros de generación son diferentes. Esta comparación reproduce las configuraciones entregadas; no permite aislar el efecto del cambio de instrucciones respecto de los demás parámetros.

## Ejecutar los 21 mensajes de prueba

Actualmente, `Run_Prompts.py` utiliza **`gemma3:4b`** de forma predeterminada, a diferencia de la demostración interactiva.

Para evaluar el modelo del video, reemplaza la lista `MODELS` de ese archivo por:

```python
MODELS = ["ministral-3:3b"]
```

Luego ejecuta:

```bash
python Run_Prompts.py
```

Si prefieres mantener la configuración actual con Gemma, descarga primero ese modelo:

```bash
ollama pull gemma3:4b
```

### Probar los tres modelos

Además de Ministral, descarga los modelos restantes:

```bash
ollama pull qwen3.5:4b
ollama pull gemma3:4b
```

Configura la lista en `Run_Prompts.py`:

```python
MODELS = ["qwen3.5:4b", "ministral-3:3b", "gemma3:4b"]
```

Ejecuta nuevamente:

```bash
python Run_Prompts.py
```

### Dónde se guardan los resultados

Cada prueba comienza con una conversación nueva.

Los resultados se guardan en una carpeta nueva:

```text
Outputs_D2/run_YYYYMMDD_HHMMSS/
```

Esta carpeta contiene:

- Subcarpetas por modelo con las respuestas en archivos `OUTPUT*.txt`.
- Un archivo `summary.tsv` que relaciona cada respuesta con su mensaje de entrada.

El resumen registra el estado de validación del JSON, los conteos de tokens, la duración, el motivo de finalización y los errores.

La numeración de las respuestas continúa entre modelos; consulta `summary.tsv` para identificar sus entradas.

**`status=ok` significa que la respuesta pudo interpretarse como JSON, no que la información extraída sea correcta.**

Evalúa el contenido utilizando `Rubrica.txt` e `Instruction_2.txt`.

El programa de pruebas ejecuta únicamente la solución; no ejecuta automáticamente la versión base.

## Solución de problemas

| Problema | Acción |
| --- | --- |
| `No module named 'ollama'` | Activa el entorno virtual y ejecuta `python -m pip install ollama`. |
| No es posible conectarse a Ollama | Inicia la aplicación Ollama o ejecuta `ollama serve`. |
| No se encuentra el modelo | Descarga la etiqueta exacta indicada en `MODEL` o `MODELS`. |
| No se encuentra `Instruction_2.txt` | Ejecuta la solución interactiva desde `Project_GenAI/Deliverable_2`. |
| La respuesta tarda en aparecer | Las llamadas esperan la respuesta completa; la carga inicial del modelo también puede tardar. |

## Notas de reproducibilidad

El programa de pruebas fija la semilla en 42, pero esto no garantiza respuestas idénticas entre distintas versiones del modelo, de Ollama o del hardware.

Para registrar tu entorno, guarda las salidas de los siguientes comandos:

```bash
python --version
python -m pip show ollama
ollama --version
ollama list
ollama show ministral-3:3b
```

Registra también el commit del repositorio y el hardware utilizado.

## Referencias de instalación

- [Guía de inicio de Ollama](https://docs.ollama.com/quickstart).
- [Cliente de Python para Ollama](https://github.com/ollama/ollama-python).
