import json
from datetime import datetime
from pathlib import Path

from ollama import chat


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
SYSTEM_PROMPT_FILE = BASE_DIR / "Instruction_2.txt"
PROMPTS_DIR = BASE_DIR / "Prompts_Separados"
OUTPUTS_DIR = BASE_DIR / "Outputs_D2"


# ============================================================
# MODELS AND GENERATION SETTINGS
# ============================================================

MODELS = [
    # "qwen3.5:4b",
    # "ministral-3:3b",
     "gemma3:4b",
]

THINK = False


OPTIONS = {
    "temperature": 0.3,
    "top_p": 0.5,
    "top_k": 10,
    "num_ctx": 4096,
    "num_predict": 4096,
    "seed": 42,
    "repeat_penalty": 1.1,
}


# ============================================================
# HELPERS
# ============================================================

def safe_folder_name(model_name):
    """Example: qwen3.5:4b -> qwen3.5_4b."""
    return model_name.replace(":", "_").replace("/", "_")


def seconds(nanoseconds):
    """Convert Ollama's nanoseconds to seconds."""
    return round((nanoseconds or 0) / 1_000_000_000, 3)


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():
    if not SYSTEM_PROMPT_FILE.is_file():
        print(f"Instruction file not found: {SYSTEM_PROMPT_FILE}")
        return

    if not PROMPTS_DIR.is_dir():
        print(f"Prompt folder not found: {PROMPTS_DIR}")
        return

    system_prompt = SYSTEM_PROMPT_FILE.read_text(
        encoding="utf-8-sig"
    ).strip()

    prompt_files = sorted(PROMPTS_DIR.glob("*.txt"))

    if not prompt_files:
        print(f"No .txt files found in: {PROMPTS_DIR}")
        return

    if not MODELS:
        print("Add at least one model to MODELS.")
        return

    run_name = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir = OUTPUTS_DIR / run_name
    run_dir.mkdir(parents=True)

    summary_lines = [
        "model\tprompt_file\toutput_file\tstatus\tinput_tokens\t"
        "output_tokens\ttotal_seconds\tdone_reason\terror"
    ]

    total = len(MODELS) * len(prompt_files)
    current = 0

    for model in MODELS:
        model_dir = run_dir / safe_folder_name(model)
        model_dir.mkdir()

        for prompt_file in prompt_files:
            current += 1
            print(f"[{current}/{total}] {model} <- {prompt_file.name}")

            prompt = prompt_file.read_text(
                encoding="utf-8-sig"
            ).strip()

            output_file = model_dir / f"OUTPUT{current}.txt"

            # New message list for every test case: no history from
            # previous prompts is passed to the model.
            messages = []

            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt,
                })

            messages.append({
                "role": "user",
                "content": prompt,
            })

            try:
                response = chat(
                    model=model,
                    messages=messages,
                    format="json",
                    think=THINK,
                    stream=False,
                    options=OPTIONS,
                )

                content = response.message.content or ""
                output_file.write_text(content, encoding="utf-8")

                # JSON mode requests JSON output. Parsing checks whether
                # this particular response is actually valid JSON.
                try:
                    json.loads(content)
                    status = "ok"
                    error_text = ""
                except json.JSONDecodeError as error:
                    status = "invalid_json"
                    error_text = str(error).replace("\t", " ").replace("\n", " ")
                    print(f"  Invalid JSON: {error_text}")

                summary_lines.append(
                    "\t".join([
                        model,
                        prompt_file.name,
                        str(output_file.relative_to(run_dir)),
                        status,
                        str(response.prompt_eval_count or 0),
                        str(response.eval_count or 0),
                        str(seconds(response.total_duration)),
                        str(response.done_reason or ""),
                        error_text,
                    ])
                )

            except Exception as error:
                error_text = f"{type(error).__name__}: {error}"
                output_file.write_text(
                    f"ERROR\n{error_text}\n",
                    encoding="utf-8",
                )

                clean_error = error_text.replace("\t", " ").replace("\n", " ")

                summary_lines.append(
                    "\t".join([
                        model,
                        prompt_file.name,
                        str(output_file.relative_to(run_dir)),
                        "error",
                        "",
                        "",
                        "",
                        "",
                        clean_error,
                    ])
                )

                print(f"  ERROR: {error_text}")

    summary_file = run_dir / "summary.tsv"
    summary_file.write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8-sig",
    )

    print("\nProcess finished.")
    print(f"Responses: {run_dir}")
    print(f"Summary: {summary_file}")


if __name__ == "__main__":
    main()