import shutil
from pathlib import Path

from PIL import Image, ImageOps, ImageEnhance, ImageFilter

WINDOWS_TESSERACT = Path(r"C:\Tesseract-OCR\tesseract.exe")


def _configure_tesseract(pytesseract) -> None:
    if shutil.which("tesseract"):
        return
    if WINDOWS_TESSERACT.exists():
        pytesseract.pytesseract.tesseract_cmd = str(WINDOWS_TESSERACT)
    else:
        raise RuntimeError("Tesseract not found. Add C:\\Tesseract-OCR to PATH.")


def extract_text(image: Image.Image) -> str:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("Install OCR support with: pip install -e '.[ocr]'") from exc
    _configure_tesseract(pytesseract)
    image = ImageOps.exif_transpose(image)
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.6).filter(ImageFilter.SHARPEN)
    lang = "hin+eng" if "hin" in pytesseract.get_languages(config="") else "eng"
    return pytesseract.image_to_string(image, lang=lang, config="--psm 6")