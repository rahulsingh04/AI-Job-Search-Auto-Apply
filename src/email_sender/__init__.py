"""Gmail email sending with deduplication and batch processing."""

__all__ = ["run_email_batch", "send_email"]


def __getattr__(name):
    """Lazy imports to avoid pulling in heavy dependencies at package level."""

    if name == "run_email_batch":
        from .batch import run_email_batch
        return run_email_batch

    if name == "send_email":
        from .sender import send_email
        return send_email

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

