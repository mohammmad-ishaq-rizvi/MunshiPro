"""Downloadable, preparatory sales and GST summaries."""
from datetime import date,datetime
from io import BytesIO
import json,os,uuid
from urllib.request import Request,urlopen
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle

def send_summary_pdf(pdf_bytes,filename,period,phone,sales,credits,gst):
    token=os.getenv("WHATSAPP_ACCESS_TOKEN"); phone_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID"); version=os.getenv("META_GRAPH_VERSION"); template=os.getenv("WHATSAPP_SUMMARY_TEMPLATE_NAME")
    if not all((token,phone_id,version,template)): raise RuntimeError("Configure WhatsApp Cloud API credentials and an approved summary template first.")
    boundary="----MunshiPro"+uuid.uuid4().hex; chunks=[]
    for name,value in (("messaging_product",b"whatsapp"),("type",b"application/pdf")):
        chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode(),value,b"\r\n"])
    chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: application/pdf\r\n\r\n".encode(),pdf_bytes,b"\r\n",f"--{boundary}--\r\n".encode()])
    req=Request(f"https://graph.facebook.com/{version}/{phone_id}/media",data=b"".join(chunks),headers={"Authorization":f"Bearer {token}","Content-Type":f"multipart/form-data; boundary={boundary}"},method="POST")
    with urlopen(req,timeout=30) as response: media_id=json.loads(response.read().decode())["id"]
    recipient="".join(c for c in phone if c.isdigit())
    if len(recipient)==10: recipient="91"+recipient
    payload={"messaging_product":"whatsapp","to":recipient,"type":"template","template":{"name":template,"language":{"code":os.getenv("WHATSAPP_SUMMARY_TEMPLATE_LANGUAGE","en_IN")},"components":[{"type":"header","parameters":[{"type":"document","document":{"id":media_id,"filename":filename}}]},{"type":"body","parameters":[{"type":"text","text":str(v)} for v in (period,f"₹{sales:,.2f}",f"₹{credits:,.2f}",f"₹{gst:,.2f}")]}]}}
    req=Request(f"https://graph.facebook.com/{version}/{phone_id}/messages",data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},method="POST")
    with urlopen(req,timeout=30) as response: return json.loads(response.read().decode())

def _week(value):
    try: return date.fromisoformat(str(value)[:10]).strftime("%G-W%V")
    except ValueError: return ""

def make_monthly_pdf(sales,credits,period=None):
    period=period or date.today().strftime("%Y-%m")
    selected=[s for s in sales if (_week(s.get("created",""))==period if "-W" in period else str(s.get("created",""))[:7]==period)]
    pending=[c for c in credits if c.get("status")=="pending"]
    total=sum(float(s.get("amount",0) or 0) for s in selected)
    upi=sum(float(s.get("amount",0) or 0) for s in selected if str(s.get("payment_mode","")).casefold()=="upi")
    cash=sum(float(s.get("amount",0) or 0) for s in selected if str(s.get("payment_mode","")).casefold()=="cash")
    gst=sum(float(s.get("tax",0) or 0) for s in selected); open_credit=sum(float(c.get("amount",0) or 0) for c in pending)
    styles=getSampleStyleSheet(); story=[Paragraph("Dukaan Digital · Shop Summary",styles["Title"]),Paragraph(f"Period: {period} · Generated {datetime.now().astimezone():%d %b %Y, %H:%M %Z}",styles["Normal"]),Spacer(1,8*mm),Paragraph("Preparatory record for your accountant. Not a GST return, tax calculation, or filing.",styles["Normal"]),Spacer(1,5*mm)]
    data=[["Metric","Amount / count"],["Recorded sales",f"₹{total:,.2f}"],["UPI sales",f"₹{upi:,.2f}"],["Cash sales",f"₹{cash:,.2f}"],["Open customer credit",f"₹{open_credit:,.2f}"],["GST recorded on invoices",f"₹{gst:,.2f}"],["Invoices / sales",str(len(selected))]]
    table=Table(data,colWidths=[105*mm,65*mm]); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#14243b")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#dce2ea")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f4f6f9")]),("PADDING",(0,0),(-1,-1),8)])); story.extend([table,Spacer(1,6*mm),Paragraph("Pending credit details",styles["Heading2"])] )
    detail=[["Customer","Due date","Amount"]]+[[c.get("customer",""),c.get("due_date",""),f"₹{float(c.get('amount',0)):,.2f}"] for c in pending]
    table=Table(detail,colWidths=[80*mm,45*mm,45*mm]); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#087f70")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#dce2ea")),("PADDING",(0,0),(-1,-1),7)])); story.append(table)
    out=BytesIO(); SimpleDocTemplate(out,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm).build(story); return out.getvalue()
