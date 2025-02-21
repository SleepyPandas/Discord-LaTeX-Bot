import google.generativeai as genai
import os

from dotenv import load_dotenv

# globals
conversation_histories = {}
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_TOKEN"))


def create_chat_session(user_input: str, user_id: int) -> str:
    history = conversation_histories.get(user_id, [])

    generation_config = {
        "temperature": .5,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 512,
        "response_mime_type": "text/plain",
    }

    # EXPERIMENTAL MODEL CAN CHANGE OR BREAK
    model = genai.GenerativeModel(
        model_name="learnlm-1.5-pro-experimental",
        system_instruction=os.getenv("SYSTEM_INSTRUCTION"),
        tools="code_execution",
    )

    # Maintains chat history using google SDK
    chat = model.start_chat(
        history=history
    )

    # Append the new user message to the conversation history.
    user_message = {"role": "user", "parts": [user_input]}
    history.append(user_message)

    if len(history) > 20:
        return reset_history(user_id)

    response = chat.send_message(
        user_input,
        generation_config=genai.GenerationConfig(**generation_config)
    )

    # Append the new user message to the conversation history.
    model_message = {"role": "model", "parts": [response.text]}
    history.append(model_message)

    conversation_histories[user_id] = history

    return response.text


def reset_history(user_id: int) -> str:
    conversation_histories[user_id] = []
    return "History cleared"
