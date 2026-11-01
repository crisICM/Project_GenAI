# Deliverable 3 — Sistema Agentico

En esta entrega continuamos con la extracción de solicitudes municipales de emergencia. Utilizamos los mismos 21 mensajes de prueba de las entregas anteriores.

La solución utiliza tres agentes con tareas distintas: suministros, contexto y auditoría. Todos ocupan el modelo **Ministral 3 3B**, ejecutado localmente con Ollama. También se utilizan herramientas en Python para calcular cantidades y comprobar las respuestas.

## Archivos importantes de la Entrega 3

| Archivo o carpeta | Función |
| --- | --- |
| `Run_Prompts_D3.py` | Ejecuta los mensajes de prueba y guarda las respuestas y los registros de ejecución. |
| `coordinador.py` | Organiza las llamadas a los agentes, aplica las correcciones solicitadas y prepara la salida final. |
| `herramientas.py` | Contiene las comprobaciones de formato, citas y operaciones aritméticas. |
| `agente_1_suministros.txt` | Instrucciones del agente que extrae los artículos solicitados y sus cantidades. |
| `agente_2_contexto.txt` | Instrucciones del agente que extrae la ubicación, las referencias, la urgencia y los requerimientos operativos. |
| `agente_3_auditor.txt` | Instrucciones del auditor que revisa las extracciones y solicita correcciones cuando corresponde. |
| `traces_legibles.py` | Convierte los registros de ejecución en archivos de texto más fáciles de leer. |
| `Prompts_separados/` | Los 21 mensajes individuales utilizados para las pruebas. |
| `Outputs_D3/` | Resultados y registros de cada ejecución. |

## Cómo funciona

Primero se ejecuta el agente de suministros y después el agente de contexto. Ambos reciben el mismo mensaje original.

El agente de suministros identifica qué se solicita y cuánto. También distingue pedidos de ofertas o ayuda ya recibida, y conserva las condiciones y dudas del mensaje.

El agente de contexto identifica dónde se necesita la ayuda, recoge las referencias de acceso y evalúa la urgencia y los requerimientos operativos.

Luego, las herramientas de Python comprueban las extracciones y realizan los cálculos declarados cuando corresponde.

El auditor recibe el mensaje original, las extracciones y los resultados de las herramientas. Compara esta información y decide si aprueba, solicita correcciones o requiere revisión manual.

Si solicita una corrección, el coordinador llama al agente correspondiente con el mensaje original, la observación del auditor y el dato que debe revisar. Después se vuelven a ejecutar las herramientas y la auditoría.

La configuración predeterminada permite **2 rondas de corrección y hasta 6 correcciones por ronda**. Esto permite hasta 3 revisiones del auditor: la inicial y una después de cada ronda.

Finalmente, Python reúne la información disponible y genera la salida.

## Instalación

Instala Python, Git y [Ollama](https://ollama.com/download).

Para ejecutar los archivos de esta entrega se utiliza Python y su biblioteca estándar. No es necesario instalar el paquete de Python `ollama`.

### 1. Obtener el repositorio

Si todavía no tienes una copia local:

```bash
git clone https://github.com/crisICM/Project_GenAI.git
cd Project_GenAI/Deliverable_3
```

Si ya tienes los archivos, abre una terminal en la carpeta `Deliverable_3`.

### 2. Iniciar Ollama y descargar el modelo

Mantén abierta la aplicación Ollama. Si el servidor todavía no está funcionando, ejecuta lo siguiente en otra terminal y déjala abierta:

```bash
ollama serve
```

Descarga el modelo:

```bash
ollama pull ministral-3:3b
```

El programa utiliza la dirección local `http://localhost:11434`.

## Ejecutar los mensajes de prueba

Ejecuta los siguientes comandos desde la carpeta `Deliverable_3`.

Para revisar los nombres y el orden de los mensajes:

```bash
python Run_Prompts_D3.py --listar
```

Este comando solo muestra la lista; no llama al modelo.

Para probar los primeros dos mensajes:

```bash
python Run_Prompts_D3.py --limite 2
```

Para ejecutar los 21 mensajes:

```bash
python Run_Prompts_D3.py
```

Los mensajes se procesan de forma secuencial. Cada caso se trabaja de manera independiente.

También puedes ejecutar un mensaje específico:

```bash
python Run_Prompts_D3.py --caso "NOMBRE_DEL_ARCHIVO.txt"
```

Reemplaza `NOMBRE_DEL_ARCHIVO.txt` por el nombre exacto que aparece al ejecutar `--listar`.

Por defecto, el programa espera encontrar 21 archivos TXT en `Prompts_separados/`. Si deseas utilizar una carpeta con otra cantidad de mensajes:

```bash
python Run_Prompts_D3.py --entradas "Mi_carpeta" --esperados 0
```

## Configuración utilizada

| Parámetro | Valor predeterminado |
| --- | --- |
| Modelo | `ministral-3:3b` |
| Temperatura | `0.0` |
| Semilla | `42` |
| Ventana de contexto | `16384` |
| Máximo de tokens generados por respuesta | `3072` |
| Tiempo máximo por llamada | `600 segundos` |
| Rondas de corrección | `2` |
| Máximo de correcciones por ronda | `6` |

Las instrucciones de cada agente están en archivos TXT separados. Para revisar o modificar una instrucción, abre el archivo del agente correspondiente.

## Dónde se guardan los resultados

Cada ejecución crea una carpeta nueva dentro de:

```text
Outputs_D3/run_.../
```

| Archivo o carpeta | Contenido |
| --- | --- |
| `entradas/` | Copia de los mensajes utilizados. |
| `fuentes/` | Copia del código y las instrucciones utilizadas en la ejecución. |
| `salidas_4/` | Respuestas finales con las cuatro claves de la tarea. |
| `salidas_7/` | Respuestas con información más detallada. |
| `resultados/` | Resultado completo de cada caso, incluyendo su estado. |
| `traces/` | Registro técnico de las llamadas, respuestas y eventos del sistema. |
| `traces_v1/` | Registro en texto para seguir la ejecución de forma más legible. |
| `resumen.csv` | Resumen de los casos ejecutados. |
| `resumen.json` | Resumen de la ejecución en formato JSON. |

La salida de cuatro claves contiene:

```json
{
  "suministros_solicitados": [],
  "direccion_objetivo": null,
  "referencias": null,
  "urgencia": 1
}
```

Para propósitos del entregable 3, solo consideremos `salidas_4/` y `traces_v1/`. Los demás archivos están pensados para guardar información que podría ser útil a evaluarse en un la siguiente entrega.

## Cómo revisar lo que hicieron los agentes

Para revisar rápidamente una respuesta, abre el archivo correspondiente en `salidas_4/`.

Para entender cómo se obtuvo, abre su registro en `traces_v1/`. Allí puedes seguir los datos recibidos por los agentes, sus respuestas, las comprobaciones de Python, la decisión del auditor y las correcciones realizadas.

Estos archivos omiten detalles técnicos como los esquemas extensos, los tiempos y los conteos de tokens.

**La carpeta `traces_v1` se genera al terminar el lote**, a partir de los registros guardados en `traces/`. Su generación no realiza llamadas adicionales al modelo.

Para generar nuevamente los registros legibles de una ejecución anterior:

```bash
python traces_legibles.py "Outputs_D3/NOMBRE_DE_LA_EJECUCION"
```

Reemplaza `NOMBRE_DE_LA_EJECUCION` por el nombre de la carpeta que deseas revisar.

## Cómo interpretar el estado del resultado

- **VALIDADA:** el sistema aprobó la respuesta y no detectó errores pendientes de validación.
- **PARCIAL:** se entrega la información disponible, pero requiere revisión.
- **ERROR:** no se pudo obtener una extracción inicial utilizable.

**VALIDADA no significa que toda la información sea correcta.** El auditor también puede pasar por alto errores, por lo que las respuestas deben evaluarse manualmente con el mismo criterio utilizado en las entregas anteriores.

## Reproducibilidad del video

Link del video: **pendiente de agregar**.

La demostración se realiza en Windows utilizando VS Code y Ollama con el modelo `ministral-3:3b`.

Ejecuta los siguientes comandos desde la carpeta `Deliverable_3`, con Ollama funcionando y el modelo descargado.

### 1. Ejecutar el primer mensaje

```bash
python Run_Prompts_D3.py --limite 1
```

Este comando procesa únicamente el primer mensaje de `Prompts_separados/`:

```text
PROMPT_01_CANTIDAD_ESPECIFICADA_NO_DIRECTA.txt
```

El mensaje describe un pedido anterior de 25 frazadas y 10 cajas de alimentos en Dichato. Luego aclara que las frazadas ya se completaron, que las cajas siguen pendientes y que cambió el lugar donde se recibe la ayuda.

Este caso permite revisar si el sistema distingue el pedido anterior de la actualización y conserva la nueva ubicación.

### 2. Esperar el resultado

Al terminar, la terminal muestra el estado del caso y la ruta donde se guardaron los resultados:

```text
Outputs_D3/run_.../
```

### 3. Revisar los mensajes de los agentes

Abre la carpeta de la ejecución recién creada y entra en:

```text
traces_v1/
```

Luego abre el archivo:

```text
caso_001_f82a183d.txt
```

En el video se revisa este registro para el input recibido: el mensaje original, la entrada recibida por el agente de suministros y su respuesta. Después se revisa lo que recibe y responde el agente de contexto.

El archivo permite seguir también las comprobaciones, la auditoría y el cierre de la ejecución. Para comprobar la respuesta final de cuatro claves, abre el archivo correspondiente en `salidas_4/`.

Los registros de `traces_v1/` se generan al terminar la ejecución a partir de los trazos técnicos guardados. No realizan llamadas adicionales al modelo.

## Solución de problemas

| Problema | Acción |
| --- | --- |
| No es posible conectarse a Ollama | Inicia la aplicación Ollama o ejecuta `ollama serve`. |
| No se encuentra el modelo | Ejecuta `ollama pull ministral-3:3b`. |
| No se encuentran las instrucciones de un agente | Comprueba que los tres archivos `agente_*.txt` estén junto a `coordinador.py`. |
| El programa indica una cantidad incorrecta de mensajes | Revisa los TXT de `Prompts_separados/`. Para trabajar con otra cantidad, utiliza `--esperados 0`. |
| No aparece la carpeta `traces_v1/` | Espera a que termine el lote y comprueba que exista `traces_legibles.py`. |
| La respuesta tarda en aparecer | Cada caso requiere varias llamadas al modelo. La carga inicial y las correcciones pueden aumentar el tiempo. |

## Entregas anteriores

- `Deliverable_1/`: versión base.
- `Deliverable_2/`: solución con descomposición de la tarea y ejemplos.
- `Deliverable_3/`: sistema multiagente con herramientas, auditoría y corrección.

## Referencias de instalación

- [Descarga de Ollama](https://ollama.com/download).
- [Guía de inicio de Ollama](https://docs.ollama.com/quickstart).
