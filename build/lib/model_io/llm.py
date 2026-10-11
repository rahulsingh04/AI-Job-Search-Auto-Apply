from langchain_ollama import ChatOllama

from .schemas import EmailResponse


# =========================================================
# 1. Load the local Ollama model
# =========================================================

llm = ChatOllama(
    model="deepseek-r1:1.5b",
    temperature=0.1,
    format="json",
    num_ctx=8192,
    num_predict=512
)


# =========================================================
# 2. Configure Pydantic structured output
# =========================================================

structured_llm = llm.with_structured_output(
    EmailResponse,
    method="json_mode",
    include_raw=True
)
