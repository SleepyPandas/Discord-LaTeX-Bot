import google.generativeai as genai
import os

from dotenv import load_dotenv

# globals
conversation_histories = {}
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_TOKEN"))


def _ensure_system_instruction_in_history(history: list, system_instruction: str | None) -> list:
    """Ensure the system instruction is represented in history for models that
    don't support the `system_instruction`/developer-instruction field.

    We store it as an initial user message (one-time) so it persists across turns.
    """
    if not system_instruction:
        return history

    if history:
        # If we've already injected it, don't add again.
        first = history[0]
        # `history` items are typically dict-like: {"role": ..., "parts": [...]}
        if isinstance(first, dict) and first.get("role") in {"user", "system"}:
            parts = first.get("parts")
            if parts and isinstance(parts, list) and isinstance(parts[0], (str, dict)):
                # Cheap check: if the first part contains the instruction text.
                if isinstance(parts[0], str) and system_instruction.strip() in parts[0]:
                    return history

    return [{"role": "user", "parts": [f"SYSTEM INSTRUCTIONS:\n{system_instruction}"]}] + history


def create_chat_session(user_input: str, user_id: int) -> str:
    history = conversation_histories.get(user_id, [])

    generation_config = {
        "temperature": .5,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 1024,
        "response_mime_type": "text/plain",
    }

    system_instruction = os.getenv("SYSTEM_INSTRUCTION")

    # NOTE: gemma-3-27b-it currently errors if you send developer/system instructions
    # via the `system_instruction` field (400: Developer instruction is not enabled).
    model = genai.GenerativeModel(
        model_name="gemma-3-27b-it",
        # system_instruction=os.getenv("SYSTEM_INSTRUCTION"),
        # tools="code_execution",
    )

    # Maintains chat history using google SDK
    chat = model.start_chat(
        history=_ensure_system_instruction_in_history(history, system_instruction)
    )

    # Guard against unbounded growth
    if len(history) > 20:
        return reset_history(user_id)

    response = chat.send_message(
        user_input,
        generation_config=genai.GenerationConfig(**generation_config)
    )

    # Persist the updated chat history returned by the SDK.
    # (start_chat seeds from `history`, and send_message extends it.)
    conversation_histories[user_id] = list(chat.history)

    return response.text


def reset_history(user_id: int) -> str:
    conversation_histories[user_id] = []
    return "History cleared"
