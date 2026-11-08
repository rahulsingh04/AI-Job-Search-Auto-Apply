from config_loader import get_model_config
from .schemas import EmailResponse

# Load model configuration from data/config
_config = get_model_config()

# =========================================================
# 1. Load the local Ollama model (with safe import handling)
# =========================================================
try:
    from langchain_ollama import ChatOllama
    llm = ChatOllama(
        model=_config.get("model_name", "deepseek-r1:1.5b"),
        temperature=_config.get("temperature", 0.1),
        format=_config.get("output_format", "json"),
        num_ctx=_config.get("context_window", 8192),
        num_predict=_config.get("max_tokens", 512),
        timeout=float(_config.get("timeout", 25.0)),
    )
    structured_llm = llm.with_structured_output(
        EmailResponse,
        method="json_mode",
        include_raw=True,
    )
except Exception:
    llm = None
    structured_llm = None

