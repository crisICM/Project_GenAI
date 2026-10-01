from ollama import chat
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

MODEL = "ministral-3:3b"

# Generation parameters
TEMPERATURE = 0.3
TOP_P = 0.5
TOP_K = 10

# Context / output
NUM_CTX = 4096
NUM_PREDICT = 4096


# Repetition control
REPEAT_PENALTY = 1.1

# Model reasoning
THINK = False

# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = Path(
    "Instruction_2.txt"
).read_text(encoding="utf-8")

# ============================================================
# CHAT
# ============================================================

messages = [{
    "role": "system",
    "content": SYSTEM_PROMPT
}
]

print(f"Chatting with {MODEL}")
print("Type 'exit' to finish.\n")


while True:

    user_message = input("You: ")

    if user_message.lower() == "exit":
        break

    messages.append({
        "role": "user",
        "content": user_message
    })

    response = chat(
        model=MODEL,

        messages=messages,

        format="json",
        think=THINK,

        options={
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "top_k": TOP_K,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "repeat_penalty": REPEAT_PENALTY
        }
    )

    assistant_message = response.message.content


    print("\nANSWER:")
    print(response.message.content)

    messages.append({
        "role": "assistant",
        "content": assistant_message
    })