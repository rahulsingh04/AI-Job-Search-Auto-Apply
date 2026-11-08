from config_loader import get_model_config
from .schemas import EmailResponse


def _build_llm():
    """Build ChatOllama instance from config; returns (llm, structured_llm)."""
    try:
        from langchain_ollama import ChatOllama
        cfg = get_model_config()
        _llm = ChatOllama(
            model=cfg.get("model_name", "deepseek-r1:1.5b"),
            temperature=cfg.get("temperature", 0.1),
            format=cfg.get("output_format", "json"),
            num_ctx=cfg.get("context_window", 8192),
            num_predict=cfg.get("max_tokens", 512),
            timeout=float(cfg.get("timeout", 25.0)),
        )
        _structured = _llm.with_structured_output(
            EmailResponse,
            method="json_mode",
            include_raw=True,
        )
        return _llm, _structured
    except Exception:
        return None, None


llm, structured_llm = _build_llm()

