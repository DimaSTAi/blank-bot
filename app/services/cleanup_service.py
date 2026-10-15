import os
import time

PDF_RETENTION_DAYS = 3


def cleanup_old_pdfs(directory: str = "app/data", retention_days: int = PDF_RETENTION_DAYS) -> int:
    """Удаляет PDF-файлы старше retention_days дней. Возвращает количество удалённых файлов."""
    now = time.time()
    cutoff = now - retention_days * 24 * 60 * 60
    removed = 0

    for filename in os.listdir(directory):
        if not filename.endswith(".pdf"):
            continue
        path = os.path.join(directory, filename)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            continue

    return removed
