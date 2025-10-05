import os, subprocess, re
from pathlib import Path
import numpy as np
import cv2, magic
from pdfminer.high_level import extract_text
from paddleocr import PaddleOCR

QUAR_DIR = Path(os.getenv("QUAR_DIR","/srv/quarantine"))
QUAR_DIR.mkdir(parents=True, exist_ok=True)

# OCR engine (CPU)
OCR = PaddleOCR(lang="es", use_angle_cls=True, det_db_box_thresh=0.4)

dni_letters = "TRWAGMYFPDXBNJZSQVHLCKE"
dni_re = re.compile(r"\b([0-9]{8})([A-Z])\b")
nie_re = re.compile(r"\b([XYZ][0-9]{7})([A-Z])\b")

def is_pdf(p: Path) -> bool:
    try:
        return magic.from_file(str(p), mime=True) == "application/pdf" or p.suffix.lower()==".pdf"
    except Exception:
        return p.suffix.lower()==".pdf"

def deskew(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thr = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    angle = 0.0
    if coords.size > 0:
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
    (h, w) = img.shape[:2]
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE), abs(angle)

def blur_score(img):
    fm = cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    return max(0.0, min((fm-60)/120, 1.0))

def contrast_score(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return np.clip((g.std()-30)/60, 0, 1)

def glare_score(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    v = hsv[:,:,2]
    sat = (v > 245).mean()
    return 1.0 - min(sat*4, 1.0)

def ocr_image(path: Path):
    img = cv2.imread(str(path))
    img, angle = deskew(img)
    result = OCR.ocr(img, cls=True)
    lines = []
    if result and result[0]:
        for r in result[0]:
            lines.append(r[1][0])
    text = "\n".join(lines)
    quality = 0.5*blur_score(img) + 0.3*contrast_score(img) + 0.2*glare_score(img)
    return text, float(quality), float(angle)

def normalize_pdf(src: Path) -> Path:
    out = src.with_suffix(".norm.pdf")
    subprocess.run(["ocrmypdf","--deskew","--clean","--optimize","3",
                    "--force-ocr",str(src),str(out)], check=True)
    return out

def validate_ids(text: str):
    v = {}
    m = dni_re.search(text)
    if m:
        num, let = int(m.group(1)), m.group(2)
        v["dni_ok"] = dni_letters[num % 23] == let
    m = nie_re.search(text)
    if m:
        num = m.group(1).replace("X","0").replace("Y","1").replace("Z","2")
        let = m.group(2)
        v["nie_ok"] = dni_letters[int(num) % 23] == let
    return v

def guess_type(text: str):
    t = text.lower()
    if "hipoteca" in t: return "hipoteca"
    if "contrato" in t: return "contrato"
    if "documento nacional de identidad" in t or "dni" in t or "número de soporte" in t:
        return "dni"
    return "desconocido"

def process_document(path: str) -> dict:
    """
    Entrada: ruta del archivo en cuarentena.
    Salida: dict con 'accept', 'quality_score', 'suggested_type', 'validations', 'reasons'
    """
    p = Path(path)
    reasons = []
    try:
        if is_pdf(p):
            norm = normalize_pdf(p)
            text = extract_text(str(norm)) or ""
            quality = 0.9  # tras ocrmypdf suele ser alto
            angle = 0.0
        else:
            text, quality, angle = ocr_image(p)

        validations = validate_ids(text)
        suggested = guess_type(text)

        accept = (quality >= 0.55) and (len(text.strip()) > 120 or suggested in ("dni","contrato","hipoteca"))
        if quality < 0.55: reasons.append("Baja nitidez/contraste/reflejos")
        if angle > 7: reasons.append("Documento muy girado")
        if suggested == "desconocido": reasons.append("Tipo de documento no reconocido")

        return {
            "accept": bool(accept),
            "quality_score": round(quality, 2),
            "suggested_type": suggested,
            "validations": validations,
            "extracted_fields": {},  # amplía con NIF, fechas, importes...
            "reasons": reasons
        }
    except Exception as e:
        return {"accept": False, "quality_score": 0.0, "suggested_type": "error",
                "validations": {}, "extracted_fields": {}, "reasons": [f"error:{e}"]}
