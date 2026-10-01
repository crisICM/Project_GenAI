# Deliverable 2 — Extracción de solicitudes de emergencia

## Archivos importantes

| Archivo o carpeta | Función |
| --- | --- |
| `Run_AI_D1.py` | Código que permite interactuar con el modelo IA con instrucciones de sus respuestas predeterminadas. En particular D1 significa que es la versión base, usada para la entrega 1  |
| `Run_AI_D2.py` | Actualización con las mejoras respecto a D1. Este lee las instrucciones desde el archivo Instructions_2 |
| `Instruction_2.txt` | Instrucciones de extracción para el modelo. Este es el utilizado para la entrega 2 y los nuevos resultados |
| `Run_Prompts.py` | Ejecuta la solución sobre todos prompts de prueba y guarda las respuestas y los datos de ejecución. |
| `Prompts_Separados/` | Los 21 mensajes individuales utilizados por el programa de pruebas. |
| `Prompts_deposito.txt` | Mensajes reunidos para consultarlos o copiarlos. No es el archivo de entrada del programa de pruebas. |
| `Rubrica.txt` | Respuestas de referencia y comentarios para evaluar manualmente la calidad de respuesta de los modelos frente a los prompts o mensajes de emergencia. |
| `Outputs_D2/` | Resultados obtenidos de Qwen, Ministral y Gemma. |
| `MODELS_AI` | Nombre de los modelos usados. |

## Instalación

Instala Python, Git y [Ollama](https://ollama.com/download).

En particular para la grabación se utiliza Windows, VS Code y Python 3.14.7.

### 1. Clonar el repositorio

```bash
git clone https://github.com/crisICM/Project_GenAI.git
cd Project_GenAI/Deliverable_2
```


### 2. Iniciar Ollama y descargar el modelo

Mantén abierta la aplicación Ollama. Si el servidor todavía no está funcionando, ejecuta lo siguiente en otra terminal y déjala abierta:

```bash
ollama serve
```

Descarga el modelo utilizado en la demostración:

```bash
ollama pull ministral-3:3b
```

## 3 Reproductibilidad del video

Link del video: https://drive.google.com/file/d/1hzm5N7h-Jtmf-oEKKrAkn3vlxcKA_Y-L/view?usp=drive_link
Ejecuta los siguientes comandos **desde la carpeta `Deliverable_2`**. 

Dentro de la carpeta se encuentran distintos archivos .py

Run_AI_D1.py: Este permite testear el modelo ministral usando el prompt instruction de la entrega 1. Dentro del mismo código es posible cambiar el modelo a ocupar. 

### 4. Ejecutar la versión base

```bash
python Run_AI_D1.py
```

Cuando aparezca `You:`, deberás pegar el prompt con el cual se desea testear el modelo. En el caso particular del video se hizo con el prompt 06 el cual se encuentra en la carpeta "Prompts_Separados"

PROMPT 06
Impecable la gestión municipal, un aplauso por las cero frazadas y las cero linternas que prometieron mandar anoche a Dichato, se nos inundó hasta el techo y todavía estamos alumbrándonos con la pantalla del celular. En la casa del portón verde somos 9 damnificados: 4 lograron rescatar su ropa de cama, así que calculen cuántos quedamos durmiendo en el suelo húmedo. Si el camión municipal llega antes de que oscurezca traigan solo las frazadas que faltan, pero si llegan tarde sumen linternas con pilas porque la matriz de la cancha explotó y no hay luz en toda la cuadra.


Espera a que aparezcan `ANSWER:` y el JSON generado, esta será la respuesta del modelo. Escribe `exit` para cerrar la ejecución del código.

### 5. Ejecutar la solución del Deliverable 2

```bash
python Run_AI_D2.py
```

Pega **el mismo mensaje**, espera el JSON y escribe `exit`.

Ambos programas muestran las respuestas en la terminal y no las guardan automáticamente. Conservan el historial de conversación hasta que se cierran.

Para probar otro mensaje independiente se puede seguir escribiendo mientras el programa está ejecutandose, esto es útil para probar distintas variaciones de un mismo prompt o distintos.

## Ejecución de los 21 mensajes de prueba (prompts)

Actualmente, `Run_Prompts.py` utiliza **`gemma3:4b`** de forma predeterminada, a diferencia de la demostración interactiva. Pero este se puede cambiar facilmente modificando la linea que indica el modelo a usar.

En particular para probar el mismo modelo del video se sugiere colocar:
MODELS = ["ministral-3:3b"]

Luego ejecuta:

```bash
python Run_Prompts.py
```

Esto permitirá ejecutar los 21 prompts que se utilizan para testear, son dados al modelo de forma secuencial de manera que las respuestas son independientes.

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

Se debe evaluar las respuestas utilizando `Rubrica.txt`.

El programa de pruebas ejecuta únicamente la solución; no ejecuta automáticamente la versión base.

## Solución de problemas

| Problema | Acción |
| --- | --- |
| `No module named 'ollama'` | Activa el entorno virtual y ejecuta `python -m pip install ollama`. |
| No es posible conectarse a Ollama | Inicia la aplicación Ollama o ejecuta `ollama serve`. |
| No se encuentra el modelo | Descarga la etiqueta exacta indicada en `MODEL` o `MODELS`. |
| No se encuentra `Instruction_2.txt` | Ejecuta la solución interactiva desde `Project_GenAI/Deliverable_2`. |
| La respuesta tarda en aparecer | Las llamadas esperan la respuesta completa; la carga inicial del modelo también puede tardar. |

## Referencias de instalación

- [Guía de inicio de Ollama](https://docs.ollama.com/quickstart).
- [Cliente de Python para Ollama](https://github.com/ollama/ollama-python).
