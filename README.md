# Deliverable 2 — Emergency request extraction

This system converts informal emergency messages in Spanish into JSON containing the supplies still requested, their quantities and units, the current delivery location, practical location references, and an urgency level from 1 to 5. Inference runs locally through Ollama.

The demonstration compares a simple prompting baseline (`Run_AI_D1.py`) with the structured instructions and examples used in Deliverable 2 (`Run_AI_D2.py`). Both interactive scripts use **`ministral-3:3b`**. The instructions address errors involving updates, offers versus requests, quantities, location references, and urgency.

## Important files

| File or folder | Purpose |
| --- | --- |
| [`Run_AI_D1.py`](Run_AI_D1.py) | Interactive baseline with an embedded system prompt. |
| [`Run_AI_D2.py`](Run_AI_D2.py) | Interactive solution loading `Instruction_2.txt`. |
| [`Instruction_2.txt`](Instruction_2.txt) | Extraction rules, urgency rubric, and complete examples. |
| [`Run_Prompts.py`](Run_Prompts.py) | Runs the solution on every test file and saves responses and execution metadata. |
| [`Prompts_Separados/`](Prompts_Separados/) | The 21 individual test messages read by the batch runner. |
| [`Prompts_deposito.txt`](Prompts_deposito.txt) | Combined messages for browsing or copying; not the batch runner's input source. |
| [`Rubrica.txt`](Rubrica.txt) | Reference outputs and comments for manual evaluation. |
| [`Outputs_D2/`](Outputs_D2/) | Previously saved runs for Qwen, Ministral, and Gemma. |
| [`MODELS_AI`](MODELS_AI) | Model notes; execution settings are defined in the Python scripts. |

## Setup

Install Python, Git, and [Ollama](https://ollama.com/download). The recording uses Windows, VS Code, and Python 3.14.7. VS Code is optional; the scripts run from a terminal. Allow enough RAM/VRAM and disk space for the downloaded model. No paid API key is needed for this local workflow.

Clone the repository and enter this folder:

```bash
git clone https://github.com/crisICM/Project_GenAI.git
cd Project_GenAI/Deliverable_2
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it using the command for your terminal:

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
.venv\Scripts\activate.bat
```

Linux/macOS:

```bash
source .venv/bin/activate
```

On systems where Python is named `python3`, use `python3 -m venv .venv`. After activation, use `python` for the remaining commands.

Install the Python dependency:

```bash
python -m pip install ollama
```

The other imports are from Python's standard library. Keep the Ollama application running. If it is not already serving requests, run this in a separate terminal and leave it open:

```bash
ollama serve
```

Download and check the demonstration model:

```bash
ollama pull ministral-3:3b
ollama list
```

## Reproduce the video comparison

Run these commands **from `Deliverable_2`**. The interactive solution reads `Instruction_2.txt` relative to the current working directory.

1. Start the baseline:

   ```bash
   python Run_AI_D1.py
   ```

2. At `You:`, paste the following message as **one line** and press Enter. It is test 06 in `Prompts_Separados/`, and is the message used in the recording:

   ```text
   Impecable la gestión municipal, un aplauso por las cero frazadas y las cero linternas que prometieron mandar anoche a Dichato, se nos inundó hasta el techo y todavía estamos alumbrándonos con la pantalla del celular. En la casa del portón verde somos 9 damnificados: 4 lograron rescatar su ropa de cama, así que calculen cuántos quedamos durmiendo en el suelo húmedo. Si el camión municipal llega antes de que oscurezca traigan solo las frazadas que faltan, pero si llegan tarde sumen linternas con pilas porque la matriz de la cancha explotó y no hay luz en toda la cuadra.
   ```

3. Wait for `ANSWER:` and the generated JSON. Type `exit` to end the baseline session.

4. Start the solution:

   ```bash
   python Run_AI_D2.py
   ```

5. Paste the **same message**, wait for the JSON, and type `exit`.

Both scripts print responses to the terminal; they do not save them automatically. Each keeps conversation history until exit. Restart the script before testing another independent message.

### What the recording shows

The baseline returns blankets and flashlights with unknown quantities, `Dichato` as the destination, no references, and urgency 5. The solution returns a quantity of 5 blankets, but also incorrectly uses `Revisión Manual` as a resource with `linternas` as its unit, and replaces the destination with `Revisión Manual`.

This example illustrates a quantity improvement and a remaining failure involving conditional requests and location extraction. It is not a fully correct solution output. Inspect whether the model preserves the known location and the green-gate reference, represents the flashlight request correctly, and justifies the urgency using the rubric in `Instruction_2.txt`.

Exact responses can vary: the interactive scripts do not set a seed, and their generation settings differ. This comparison reproduces the submitted configurations; it does not isolate the prompt change from all other settings.

## Run all 21 test messages

`Run_Prompts.py` currently defaults to **`gemma3:4b`**, which differs from the interactive demonstration. To evaluate the demonstration model, replace the `MODELS` list in that file with:

```python
MODELS = ["ministral-3:3b"]
```

Then run:

```bash
python Run_Prompts.py
```

To keep the current Gemma default, first run `ollama pull gemma3:4b`. For a three-model run, download the other models and set:

```bash
ollama pull qwen3.5:4b
ollama pull gemma3:4b
```

```python
MODELS = ["qwen3.5:4b", "ministral-3:3b", "gemma3:4b"]
```

Each test starts with a fresh conversation. Results are written to a new `Outputs_D2/run_YYYYMMDD_HHMMSS/` folder, with model subfolders containing `OUTPUT*.txt` and a `summary.tsv` mapping each response to its input. The summary records JSON parsing status, token counts, duration, stop reason, and errors. Output numbering continues across models; use the summary to identify inputs.

**`status=ok` means the response parsed as JSON, not that its extracted information is correct.** Evaluate content against `Rubrica.txt` and `Instruction_2.txt`. The batch runner evaluates the solution only; it does not automatically run the baseline.

## Troubleshooting and reproducibility

| Problem | Action |
| --- | --- |
| `No module named 'ollama'` | Activate the virtual environment and run `python -m pip install ollama`. |
| Cannot connect to Ollama | Start the Ollama application or `ollama serve`. |
| Model not found | Pull the exact tag selected in `MODEL` or `MODELS`. |
| `Instruction_2.txt` not found | Run the interactive solution from `Project_GenAI/Deliverable_2`. |
| Response takes time to appear | The calls wait for the complete response; initial model loading can also take time. |

The batch runner sets seed 42; this does not guarantee identical output across model builds, Ollama versions, or hardware. To record your environment, save the output of `python --version`, `python -m pip show ollama`, `ollama --version`, `ollama list`, and `ollama show ministral-3:3b`, along with the repository commit and hardware used.

Setup references: [Ollama quickstart](https://docs.ollama.com/quickstart) and [Ollama Python client](https://github.com/ollama/ollama-python).
