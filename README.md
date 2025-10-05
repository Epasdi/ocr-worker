# ocr-worker (RQ + PaddleOCR/OCRmyPDF)

Worker RQ que procesa documentos en segundo plano. Lee de la cola `ocr`.

## Variables
- `REDIS_URL=redis://redis:6379/0`
- `QUAR_DIR=/srv/quarantine`

## Despliegue en Coolify
- Build pack: **Dockerfile**
- **Sin puerto**
- **Volume**: host `/srv/quarantine` -> container `/srv/quarantine`

El API enviará trabajos con `ocr_task.process_document(path)`.
