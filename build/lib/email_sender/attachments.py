from pathlib import Path
from email.mime.application import MIMEApplication


def normalize_attachments(attachments=None) -> list[Path]:
    """Normalize and validate PDF attachment paths."""

    if attachments is None:
        return []

    if isinstance(attachments, (str, Path)):
        attachments = [attachments]

    if not isinstance(attachments, (list, tuple)):
        raise TypeError(
            "attachments must be a path, list of paths, "
            "tuple of paths, or None."
        )

    paths = []

    for item in attachments:
        path = Path(item).expanduser()

        if not path.is_file():
            raise FileNotFoundError(
                f"Attachment not found: {path}"
            )

        if path.suffix.lower() != ".pdf":
            raise ValueError(
                f"Only PDF attachments are supported: {path}"
            )

        paths.append(path)

    return paths


def attach_pdf_files(message, attachments=None) -> None:
    """Attach validated PDF files to a MIME email message."""

    for path in normalize_attachments(attachments):
        with path.open("rb") as file:
            pdf = MIMEApplication(
                file.read(),
                _subtype="pdf"
            )

        pdf.add_header(
            "Content-Disposition",
            "attachment",
            filename=path.name
        )

        message.attach(pdf)
