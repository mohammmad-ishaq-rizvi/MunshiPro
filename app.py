import sys, json, os, mimetypes
from pathlib import Path
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).parent/"src"))
import pandas as pd
import streamlit as st
from dukaan.core import invoice_totals, parse_order, parse_ledger_text, file_hash
from dukaan.store import Store
from dukaan.extract import extract, normalize
from dukaan.gemma import parse_voice_order, read_ledger_image
from dukaan.reports import make_monthly_pdf, send_summary_pdf
from dukaan.reminders import run_scheduler

st.set_page_config(page_title="Dukaan Digital",page_icon="📒",layout="wide")
st.markdown("""<style>
:root{--navy:#14243b;--indigo:#4659d9;--teal:#087f70;--saffron:#e8a126;--paper:#f4f6f9;--line:#e1e6ee;--ink:#19283d;--muted:#617087}
.stApp{background:var(--paper);color:var(--ink)}.block-container{max-width:1380px;padding:1.3rem 2rem 3rem}
[data-testid="stSidebar"]{background:var(--navy)}[data-testid="stSidebar"] *{color:#eef3fb}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);padding:15px 18px;border-radius:8px;box-shadow:0 2px 8px #14243b0a}
[data-testid="stMetricValue"]{color:var(--navy)}[data-testid="stMetricLabel"]{color:var(--muted)}
.brand{background:linear-gradient(112deg,#14243b 0%,#283f72 72%,#087f70 140%);color:white;padding:22px 26px;border-radius:8px;margin:4px 0 22px;box-shadow:0 8px 22px #14243b1a}
.brand h2{font-size:25px;margin:0 0 4px}.brand p{margin:0;color:#dce8fa;font-size:14px}
div.stButton>button[kind="primary"]{background:var(--indigo);border:0;border-radius:7px;font-weight:650;min-height:44px}
div.stButton>button{border-radius:7px;border-color:#d2d9e4;min-height:40px}
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{border:1px solid var(--line);border-radius:8px;overflow:hidden}
[data-testid="stFileUploader"]{background:#fff;border:1px dashed #8998b3;border-radius:10px;padding:8px}
h1,h2,h3{color:var(--navy)}.stCaption{color:var(--muted)}
@media(max-width:700px){.block-container{padding:.8rem .8rem 2rem}.brand{padding:17px}.brand h2{font-size:21px}}
</style>""",unsafe_allow_html=True)
L={"English":{"nav":["Overview","Voice billing","Khata & reminders","Smart inventory","Monthly reports","Documents & analysis","Ledger","Invoice history"],"title":"Dukaan Digital","sub":"Your shop’s digital munim · Powered by Gemma 4","new":"Create a bill","draft":"Review your bill","confirm":"Confirm and issue invoice","upload":"Upload a bill, invoice, receipt, or ledger","review":"Review extracted information before saving","no_data":"No saved business data yet.","search":"Search invoices","lang":"Language","tax":"GST rate (%)","tax_type":"Tax treatment","customer":"Customer (optional)","record":"Save reviewed records","error":"Needs your review","recent":"Recent invoices","revenue":"Recorded invoice value","docs":"Documents processed","lines":"Review extracted rows","ledger":"Ledger entries","analyze":"Analyze document","english":"English","hindi":"हिन्दी"},"हिन्दी":{"nav":["डैशबोर्ड","आवाज़ से बिल","उधार और रिमाइंडर","स्मार्ट इन्वेंटरी","मासिक रिपोर्ट","दस्तावेज़ और विश्लेषण","बही-खाता","बिल इतिहास"],"title":"दुकान डिजिटल","sub":"आपकी दुकान का डिजिटल मुनीम · Gemma 4 द्वारा संचालित","new":"नया बिल बनाएं","draft":"बिल जांचें","confirm":"पुष्टि करें और बिल जारी करें","upload":"बिल, रसीद या बही-खाता अपलोड करें","review":"सहेजने से पहले निकली जानकारी जांचें","no_data":"अभी कोई व्यवसाय रिकॉर्ड सहेजा नहीं है।","search":"बिल खोजें","lang":"भाषा","tax":"GST दर (%)","tax_type":"कर का प्रकार","customer":"ग्राहक (वैकल्पिक)","record":"जांचे हुए रिकॉर्ड सहेजें","error":"जांच आवश्यक","recent":"हाल के बिल","revenue":"दर्ज बिल राशि","docs":"प्रसंस्कृत दस्तावेज़","lines":"निकली पंक्तियां जांचें","ledger":"बही-खाता प्रविष्टियां","analyze":"दस्तावेज़ विश्लेषण","english":"English","hindi":"हिन्दी"}}
TODAY=datetime.now(ZoneInfo("Asia/Kolkata")).date()
if "lang" not in st.session_state: st.session_state.lang="English"
st.session_state.lang=st.sidebar.selectbox("Language / भाषा",["English","हिन्दी"],index=0 if st.session_state.lang=="English" else 1)
t=L[st.session_state.lang]; st.markdown(f'<div class="brand"><h2>{t["title"]}</h2><p>{t["sub"]}</p></div>',unsafe_allow_html=True)
db=Store(Path(os.getenv("DUKAAN_DB_PATH", str(Path(__file__).parent/"dukaan.sqlite3"))))
if all(os.getenv(k) for k in ("WHATSAPP_ACCESS_TOKEN","WHATSAPP_PHONE_NUMBER_ID","META_GRAPH_VERSION","WHATSAPP_TEMPLATE_NAME")):
    @st.cache_resource
    def _start_reminder_scheduler(path): return run_scheduler(path)
    _start_reminder_scheduler(str(db.path))
icons=["⌂","◉","₹","▦","▤","▧","≡","▤"]
menu_labels=[f"{icon}  {label}" for icon,label in zip(icons,t["nav"])]
requested_page=st.session_state.pop("quick_nav",None)
if requested_page in t["nav"]: st.session_state.page_nav=menu_labels[t["nav"].index(requested_page)]
if st.session_state.get("page_nav") not in menu_labels: st.session_state.page_nav=menu_labels[0]
page=st.sidebar.radio("MENU / मेनू",menu_labels,key="page_nav",label_visibility="visible")
page=t["nav"][[f"{icon}  {label}" for icon,label in zip(icons,t["nav"])].index(page)]
invoices=db.invoices()

if page==t["nav"][0]:
    st.subheader(("Good day. Here’s your shop at a glance." if st.session_state.lang=="English" else "नमस्ते, आज आपकी दुकान का हाल।")); q1,q2,q3=st.columns(3)
    q1.metric(t["recent"],len(invoices));q2.metric(t["revenue"],f"₹{sum(float(x['total']) for x in invoices):,.2f}");q3.metric(t["docs"],len(db.documents()))
    st.subheader(t["recent"]); search=st.text_input(t["search"])
    rows=[i for i in invoices if search.casefold() in (i["number"]+i["customer"]).casefold()]
    if rows: st.dataframe(pd.DataFrame(rows)[["number","created","customer","status","total"]],use_container_width=True,hide_index=True)
    else:
        st.info(t["no_data"])
        a,b,c=st.columns(3)
        with a:
            st.markdown("#### 🎙️ Voice billing")
            st.caption("Create a reviewed invoice by speaking or typing an order.")
            if st.button("Create your first bill →",key="quick_bill"): st.session_state.quick_nav=t["nav"][1]
        with b:
            st.markdown("#### ▧ Upload records")
            st.caption("Bring in sales sheets, receipts, or ledger pages.")
            if st.button("Analyze a document →",key="quick_upload"): st.session_state.quick_nav=t["nav"][5]
        with c:
            st.markdown("#### ≡ Digital ledger")
            st.caption("Review extracted entries and export verified records.")
            if st.button("Open ledger →",key="quick_ledger"): st.session_state.quick_nav=t["nav"][6]
    if invoices:
        dates=pd.DataFrame(invoices); dates["created"]=pd.to_datetime(dates.created); dates["total"]=pd.to_numeric(dates.total); st.write("Revenue by date / तारीख के अनुसार बिक्री");st.bar_chart(dates.groupby(dates.created.dt.date).total.sum())

elif page==t["nav"][1]:
    st.subheader(t["new"]); st.caption("Speak in Hindi, English, or Hinglish. Verify every detected item, amount and tax before issuing.")
    speech=""
    try:
        from streamlit_mic_recorder import speech_to_text
        speech=speech_to_text(language="hi-IN",start_prompt="🎙️ Speak / बोलें",stop_prompt="■ Stop / रोकें",key="billing_mic") or ""
        if speech: st.success("Speech captured. Review the transcript below.")
    except ImportError: st.caption("Microphone speech capture requires the optional streamlit-mic-recorder package. Typed order is available below.")
    order=st.text_area("Order / ऑर्डर",value=speech,placeholder="दो किलो चावल 60 रुपये किलो और एक तेल 150 रुपये",height=85)
    p1,p2=st.columns(2)
    with p1:
        if st.button("✨ Parse with Gemma 4",type="primary",use_container_width=True):
            try: st.session_state.bill_draft=parse_voice_order(order)
            except Exception as e: st.error(f"Gemma 4 could not parse this order: {e}")
    with p2:
        if st.button("Use local parser / स्थानीय विकल्प",use_container_width=True): st.session_state.bill_draft=parse_order(order,{})
    if st.session_state.get("bill_draft") is not None:
        st.write("#### "+t["draft"]); edit=st.data_editor(pd.DataFrame(st.session_state.bill_draft),num_rows="dynamic",use_container_width=True,hide_index=True)
        customer=st.text_input(t["customer"]); rate=st.number_input(t["tax"],0.,100.,0.,.5); treatment=st.selectbox(t["tax_type"],["none","intra-state","inter-state"]); payment_mode=st.selectbox("Payment method / भुगतान",["Cash","UPI","Card","Credit"])
        if payment_mode=="Credit":
            credit_phone=st.text_input("Customer WhatsApp number (10 digits)"); credit_due=st.date_input("Payment due date",value=TODAY); merchant_upi=st.text_input("Your UPI ID for the pay link (optional)")
        try:
            items=edit.to_dict("records"); totals=invoice_totals(items,rate,0,treatment)
            a,b,c=st.columns(3);a.metric("Subtotal",f"₹{totals['subtotal']:,.2f}");b.metric("GST",f"₹{totals['tax']:,.2f}");c.metric("Total",f"₹{totals['total']:,.2f}")
            if st.button(t["confirm"],type="primary"):
                if any(not str(i.get("product","")).strip() or i.get("unit_price") is None or float(i["unit_price"])<=0 for i in items): st.error("Fill in each product and price before issuing.")
                else:
                    if payment_mode=="Credit" and (not customer.strip() or len("".join(c for c in credit_phone if c.isdigit()))<10): st.error("Enter the customer's name and a valid WhatsApp number for a credit invoice.")
                    else:
                        number=db.add_invoice(customer,items,totals,payment_mode)
                        if payment_mode=="Credit": db.add_credit(customer,credit_phone,totals["total"],credit_due.isoformat(),f"Invoice {number}",merchant_upi)
                        st.session_state.last_invoice=(number,items,totals,customer); st.session_state.pop("bill_draft",None); st.success("Invoice issued: "+number+" · Stock adjusted for tracked products.")
        except Exception as e: st.error(str(e))
    if st.session_state.get("last_invoice"):
        number,items,totals,customer=st.session_state.last_invoice
        st.markdown(f"### Invoice {number}\nCustomer: {customer or '—'}\n\nItems: {len(items)} &nbsp; | &nbsp; Total: ₹{totals['total']:,.2f}")
        html=f"<h1>Dukaan Digital</h1><h2>Invoice {number}</h2><p>Customer: {customer or '—'}</p><table border='1' cellpadding='8'><tr><th>Product</th><th>Qty</th><th>Unit price</th><th>Total</th></tr>"+"".join(f"<tr><td>{i['product']}</td><td>{i['quantity']}</td><td>₹{i['unit_price']}</td><td>₹{float(i['quantity'])*float(i['unit_price']):.2f}</td></tr>" for i in items)+f"</table><h3>Total ₹{totals['total']}</h3>"
        st.download_button("Download printable invoice",html,"invoice.html","text/html")

elif page==t["nav"][2]:
    st.subheader("Khata · credit reminders / उधार रिमाइंडर")
    with st.form("credit_form"):
        st.markdown("#### Record a customer’s udhaar")
        ca,cb=st.columns(2); customer_name=ca.text_input("Customer name"); customer_phone=cb.text_input("WhatsApp number (10 digits)")
        cc,cd=st.columns(2); credit_amount=cc.number_input("Amount (₹)",min_value=1.0,step=10.0); due=cd.date_input("Reminder date",value=TODAY)
        ce,cf=st.columns(2); upi_id=ce.text_input("Your UPI ID (optional)",placeholder="shop@upi"); note=cf.text_input("Note (optional)")
        if st.form_submit_button("Save credit and schedule reminder",type="primary"):
            if not customer_name.strip() or len("".join(c for c in customer_phone if c.isdigit()))<10: st.error("Enter a customer name and valid WhatsApp number.")
            else: db.add_credit(customer_name,customer_phone,credit_amount,due.isoformat(),note,upi_id); st.success("Saved. The reminder is queued for the due date.")
    credits=db.credits()
    if credits:
        st.markdown("#### Outstanding balances")
        for credit in credits:
            due_label="Due today" if credit["due_date"]==TODAY.isoformat() else ("Overdue" if credit["due_date"]<TODAY.isoformat() else "Due "+credit["due_date"])
            st.write(f"**{credit['customer']}** · ₹{float(credit['amount']):,.2f} · {due_label} · {credit['note'] or '—'}")
            digits="".join(c for c in credit["phone"] if c.isdigit())[-10:]; pay=f"upi://pay?pa={quote(credit['upi_id'])}&pn={quote(credit['customer'])}&am={quote(str(credit['amount']))}&cu=INR" if credit["upi_id"] else ""
            message=f"Namaste {credit['customer']}, a friendly reminder that ₹{float(credit['amount']):,.2f} is due on {credit['due_date']}. {('Pay here: '+pay) if pay else 'Please contact the shop to pay by UPI.'} Dhanyavaad!"
            a,b=st.columns([1,4]); a.link_button("Send WhatsApp nudge",f"https://wa.me/91{digits}?text={quote(message)}",use_container_width=True)
            if b.button("Mark paid",key=f"paid_{credit['id']}"): db.settle_credit(credit["id"]); st.rerun()
    else: st.info("No pending khata balances.")
    if all(os.getenv(k) for k in ("WHATSAPP_ACCESS_TOKEN","WHATSAPP_PHONE_NUMBER_ID","META_GRAPH_VERSION","WHATSAPP_TEMPLATE_NAME")): st.success("Automatic WhatsApp delivery is enabled for due balances at 9:00 AM India time.")
    else: st.info("Automatic delivery needs WhatsApp Cloud API credentials and an approved template. Use the one-tap WhatsApp link meanwhile.")

elif page==t["nav"][3]:
    st.subheader("Voice-based smart inventory / आवाज़ से इन्वेंटरी")
    with st.form("stock_form"):
        a,b=st.columns(2); product=a.text_input("Product name"); quantity=b.number_input("Current quantity",min_value=0.0,step=1.0)
        c,d=st.columns(2); threshold=c.number_input("Low-stock threshold",min_value=0.0,value=3.0,step=1.0); unit=d.text_input("Unit",value="pcs")
        e,f=st.columns(2); supplier=e.text_input("Wholesaler WhatsApp (optional)"); supplier_msg=f.text_input("Reorder message",value="Namaste, please send {quantity} {unit} of {product}.")
        if st.form_submit_button("Save stock item",type="primary"):
            if product.strip(): db.upsert_stock(product,quantity,threshold,unit,supplier,supplier_msg); st.success("Stock level saved.")
            else: st.error("Enter a product name.")
    stock=db.inventory()
    if stock:
        st.dataframe(pd.DataFrame(stock)[["product","quantity","unit","threshold","supplier_phone"]],use_container_width=True,hide_index=True)
        low=[i for i in stock if i["quantity"]<=i["threshold"]]
        for item in low:
            st.warning(f"{item['product']} is low: {item['quantity']:g} {item['unit']} left (alert at {item['threshold']:g}).")
            if item["supplier_phone"]:
                digits="".join(c for c in item["supplier_phone"] if c.isdigit())[-10:]; message=item["supplier_message"].replace("{product}",item["product"]).replace("{quantity}",str(max(item["threshold"]*2-item["quantity"],1))).replace("{unit}",item["unit"])
                st.link_button(f"Reorder {item['product']} on WhatsApp",f"https://wa.me/91{digits}?text={quote(message)}")
        if not low: st.success("Stock looks healthy. Tracked quantities update when you issue a bill.")
    else: st.info("Add stock items to get low-stock alerts. Issued bills automatically reduce matching product quantities.")

elif page==t["nav"][4]:
    st.subheader("GST & income summary / GST और आय सारांश")
    selected_date=st.date_input("Choose a date in the period",value=TODAY); period_kind=st.radio("Report period",["Month","Week"],horizontal=True)
    period=selected_date.strftime("%Y-%m") if period_kind=="Month" else selected_date.strftime("%G-W%V")
    sales=db.sales(); credits=db.credits(include_paid=True)
    subset=[x for x in sales if (str(x["created"])[:7]==period if period_kind=="Month" else date.fromisoformat(str(x["created"])[:10]).strftime("%G-W%V")==period)]
    total=sum(float(x["amount"]) for x in subset); upi=sum(float(x["amount"]) for x in subset if x["payment_mode"].casefold()=="upi"); cash=sum(float(x["amount"]) for x in subset if x["payment_mode"].casefold()=="cash"); gst=sum(float(x.get("tax",0)) for x in subset); pending=sum(float(x["amount"]) for x in credits if x["status"]=="pending")
    a,b,c=st.columns(3); a.metric("Recorded sales",f"₹{total:,.2f}"); b.metric("UPI / cash",f"₹{upi:,.2f} / ₹{cash:,.2f}"); c.metric("Open credit",f"₹{pending:,.2f}")
    st.metric("GST explicitly recorded on invoices (estimate)",f"₹{gst:,.2f}"); st.caption("Uses only recorded transactions and tax rates. This is not a GST filing.")
    pdf=make_monthly_pdf(sales,credits,period); filename=f"dukaan-summary-{period}.pdf"
    st.download_button("Download PDF for accountant",pdf,filename,"application/pdf",type="primary")
    owner_phone=st.text_input("Shop owner WhatsApp number (include country code)")
    if st.button("Send this PDF to WhatsApp"):
        if not owner_phone.strip(): st.error("Enter the shop owner’s WhatsApp number.")
        else:
            try: send_summary_pdf(pdf,filename,period,owner_phone,total,pending,gst); st.success("Summary PDF sent to WhatsApp.")
            except Exception as e: st.error(f"Could not send the PDF: {e}")
    if not os.getenv("WHATSAPP_SUMMARY_TEMPLATE_NAME"): st.caption("Direct PDF delivery requires an approved WhatsApp template with a document header and four body parameters: period, sales, open credit, recorded GST.")

elif page==t["nav"][5]:
    st.subheader(t["upload"]); uploaded=st.file_uploader(t["upload"],type=["csv","xlsx","xls","pdf","png","jpg","jpeg","webp","tif","tiff"])
    if uploaded and st.button(t["analyze"],type="primary"):
        try:
            raw=uploaded.getvalue(); docid=db.add_document(file_hash(raw),uploaded.name,raw,"upload")
            if docid is None: st.warning("This exact document was already uploaded; duplicate prevented.")
            else:
                content,kind=extract(uploaded); st.session_state.extracted=(docid,kind,content,uploaded.name)
        except Exception as e: st.error(str(e))
    if st.session_state.get("extracted"):
        docid,kind,content,name=st.session_state.extracted;st.write("#### "+t["review"]);st.caption("Source retained: "+name)
        if kind=="text":
            st.text_area("Extracted original text",content,height=200,key="ocr_text")
            is_ledger=st.checkbox("This is a handwritten ledger / यह हस्तलिखित बही है")
            parsed=parse_ledger_text(st.session_state.ocr_text) if is_ledger else []
            if parsed:
                ed=st.data_editor(pd.DataFrame(parsed),num_rows="dynamic",use_container_width=True,hide_index=True)
                if st.button(t["record"]): db.add_entries(docid,ed.to_dict("records")); st.success("Reviewed entries saved")
            else: st.info("Text is preserved for verification. Confirm the document type and correct extracted rows before saving structured data.")
            source=db.db.execute("SELECT filename,content FROM documents WHERE id=?",(docid,)).fetchone()
            if source and Path(source["filename"]).suffix.lower() in (".png",".jpg",".jpeg",".webp",".tif",".tiff"):
                if os.getenv("GEMINI_API_KEY") and st.button("✨ Read handwritten page with Gemma 4 vision",key=f"gemma_ledger_{docid}"):
                    try: st.session_state.gemma_ledger=(docid,read_ledger_image(source["content"],mimetypes.guess_type(source["filename"])[0] or "image/jpeg"))
                    except Exception as e: st.error(f"Gemma could not read this image: {e}")
                elif not os.getenv("GEMINI_API_KEY"): st.caption("Add GEMINI_API_KEY to enable Gemma 4 multimodal handwriting recognition.")
                if st.session_state.get("gemma_ledger",(None,))[0]==docid:
                    st.markdown("#### Gemma 4 transcription · review every value")
                    gemma_edit=st.data_editor(pd.DataFrame(st.session_state.gemma_ledger[1]),num_rows="dynamic",use_container_width=True,hide_index=True,key=f"gemma_rows_{docid}")
                    if st.button("Save reviewed Gemma rows",key=f"gemma_save_{docid}"): db.add_entries(docid,gemma_edit.to_dict("records")); st.success("Reviewed Gemma rows saved.")
        else:
            try:
                frame=normalize(content); st.dataframe(frame,use_container_width=True,hide_index=True)
                edited=st.data_editor(frame,num_rows="dynamic",use_container_width=True,hide_index=True)
                if st.button(t["record"]):
                    db.add_entries(docid,edited.to_dict("records")); st.success("Reviewed rows saved")
                st.subheader("Actual data summary")
                amount=edited.line_total.sum(); a,b=st.columns(2);a.metric("Document total",f"₹{amount:,.2f}");b.metric("Products",int(edited.product.nunique()))
                st.bar_chart(edited.groupby("product").line_total.sum().sort_values(ascending=False))
                st.download_button("Download analysis CSV",edited.to_csv(index=False).encode("utf-8-sig"),"business-analysis.csv")
            except Exception as e: st.error(str(e))
    docs=db.documents()
    if docs:
        st.write("#### Stored source documents");st.dataframe(pd.DataFrame(docs),use_container_width=True,hide_index=True)

elif page==t["nav"][6]:
    st.subheader(t["ledger"]);st.caption("Upload a ledger in Documents & analysis. Low-confidence OCR entries need manual verification.")
    entries=db.db.execute("SELECT payload,reviewed,created FROM entries ORDER BY id DESC").fetchall()
    if entries:
        data=pd.DataFrame([{**json.loads(r["payload"]),"saved":r["created"]} for r in entries]);edit=st.data_editor(data,num_rows="dynamic",use_container_width=True,hide_index=True)
        st.download_button("Export ledger CSV",edit.to_csv(index=False).encode("utf-8-sig"),"verified-ledger.csv")
    else: st.info(t["no_data"])
elif page==t["nav"][7]:
    st.subheader(t["recent"]); needle=st.text_input(t["search"]); rows=[r for r in invoices if needle.casefold() in (r["number"]+r["customer"]).casefold()]
    if rows: st.dataframe(pd.DataFrame(rows)[["number","created","customer","status","subtotal","tax","total"]],use_container_width=True,hide_index=True)
    else: st.info(t["no_data"])
st.divider();st.caption("Gemma 4 helps interpret Hindi voice transcripts and handwritten ledger images. AI/OCR output is a draft; review before saving. Tax summaries are preparatory, not GST filings.")
