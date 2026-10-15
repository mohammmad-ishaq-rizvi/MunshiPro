from pathlib import Path
import pandas as pd

def extract(upload):
    ext=Path(upload.name).suffix.lower(); data=upload.getvalue()
    if ext==".csv": return pd.read_csv(upload),"table"
    if ext in (".xlsx",".xls"): return pd.read_excel(upload),"table"
    if ext==".pdf":
        try:
            import pymupdf
            doc=pymupdf.open(stream=data,filetype="pdf"); text="\n".join(p.get_text() for p in doc)
            if text.strip(): return text,"text"
            raise ValueError("PDF contains no selectable text. Convert pages to images and use OCR.")
        except ImportError: raise ValueError("Install PDF support with pip install pymupdf")
    if ext in (".png",".jpg",".jpeg",".webp",".tif",".tiff"):
        try:
            from PIL import Image,ImageOps,ImageEnhance
            import pytesseract
            import io
            im=ImageOps.autocontrast(ImageOps.grayscale(Image.open(io.BytesIO(data))))
            return pytesseract.image_to_string(im,lang="eng+hin"),"text"
        except ImportError: raise ValueError("Image OCR requires Tesseract plus pip install -e '.[ocr]'")
    raise ValueError("Use CSV, Excel, PDF, or an image (PNG/JPG/WEBP/TIFF).")

def normalize(frame):
    frame=frame.copy(); frame.columns=[str(c).strip().casefold().replace(" ","_") for c in frame.columns]
    aliases={"item":"product","description":"product","name":"product","qty":"quantity","price":"unit_price","amount":"line_total","total":"line_total","bill_date":"date"}
    frame=frame.rename(columns={c:aliases.get(c,c) for c in frame.columns})
    if "product" not in frame: frame["product"]=""
    if "quantity" not in frame: frame["quantity"]=1
    price="unit_price" if "unit_price" in frame else "line_total" if "line_total" in frame else None
    if not price: raise ValueError("Could not identify price or amount column")
    frame[price]=pd.to_numeric(frame[price].astype(str).str.replace(",","",regex=False),errors="coerce")
    frame["quantity"]=pd.to_numeric(frame["quantity"],errors="coerce")
    if frame[price].isna().any() or frame.quantity.isna().any(): raise ValueError("Some quantity or amount fields are unclear; correct the source file")
    frame["line_total"]=frame[price] if price=="line_total" else frame[price]*frame.quantity
    return frame
