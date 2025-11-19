import os
from langchain_google_genai import ChatGoogleGenerativeAI

def get_llm_client(model_name: str) -> ChatGoogleGenerativeAI:
    """Initializes and returns the LangChain client for the Google Gemini LLM.

    This function ensures that the necessary environment variable for the API
    key is set before creating the client. It follows the "Fail Loudly"
    principle by raising an error if the key is missing.

    Args:
        model_name: The name of the Gemini model to use (e.g., "gemini-2.5-flash").

    Returns:
        An instance of `ChatGoogleGenerativeAI` configured with the specified model.

    Raises:
        ValueError: If the `GOOGLE_API_KEY` environment variable is not set.
    """
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError(
            "GOOGLE_API_KEY environment variable not set. "
            "Please set it in the scripts/.env file."
        )

    llm = ChatGoogleGenerativeAI(model=model_name)
    return llm
