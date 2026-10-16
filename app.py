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
@import url('https://fonts.googleapis.com/css2?family=Hind:wght@400;500;600;700&family=Rozha+One&display=swap');
:root{color-scheme:light;--bottle:#0d3b31;--bottle2:#14514a;--paper:#eef3ec;--rule:#dbe5d8;--card:#fbfdf9;--line:#d3ddd0;--ink:#13221d;--muted:#5a6a63;--haldi:#f1b323;--haldi-d:#c58a00;--late:#c2412d;--soon:#2e7d5b;--today:#d99a06}
html,body,.stApp,[data-testid="stAppViewContainer"]{font-family:'Hind',system-ui,sans-serif;color:var(--ink)}
.stApp{background:repeating-linear-gradient(to bottom,transparent 0 35px,var(--rule) 35px 36px),var(--paper);background-attachment:local}
[data-testid="stHeader"]{background:transparent}
.block-container{max-width:1320px;padding:1.1rem 2.2rem 3rem}
p,li,label,input,textarea,button,.stMarkdown{font-family:'Hind',system-ui,sans-serif}
h1,h2,h3,h4{font-family:'Hind',sans-serif;color:var(--bottle);letter-spacing:-.01em}
[data-testid="stHeading"] h3{font-family:'Rozha One','Hind',serif;font-weight:400;font-size:1.85rem;line-height:1.25;padding-bottom:.45rem;margin-bottom:.4rem;position:relative}
[data-testid="stHeading"] h3::after{content:"";position:absolute;left:0;bottom:0;width:54px;height:4px;border-radius:2px;background:var(--haldi)}
h4{font-weight:700}
.stCaption,[data-testid="stCaptionContainer"]{color:var(--muted)}

/* sidebar */
[data-testid="stSidebar"]{background:linear-gradient(180deg,var(--bottle) 0%,#0a2e26 100%);border-right:0}
[data-testid="stSidebar"] *{color:#e6f1ea}
[data-testid="stSidebar"] [data-baseweb="select"]>div{background:#12483f;border:1px solid #2a6a5d;border-radius:10px}
[data-testid="stSidebar"] [role="radiogroup"]{gap:3px}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:10px 14px;border-radius:10px;border-left:3px solid transparent;transition:background .15s,border-color .15s,transform .15s;cursor:pointer;width:100%}
[data-testid="stSidebar"] [role="radiogroup"] label>div:first-child{display:none}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#14514a;transform:translateX(2px)}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#17584f;border-left-color:var(--haldi);font-weight:700}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{color:#fff}
.sb-brand{display:flex;gap:12px;align-items:center;padding:6px 4px 18px;border-bottom:1px solid #245f54;margin-bottom:14px}
.sb-mark{width:46px;height:46px;border-radius:12px;background:var(--haldi);color:#2a1d00!important;display:grid;place-items:center;font:400 26px 'Rozha One',serif;flex:none}
.sb-brand b{display:block;font-size:19px;line-height:1.1;color:#fff}.sb-brand span{font-size:12.5px;color:#a9cbbd}

/* top bar */
.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:2px 0 18px;padding:10px 4px;border-bottom:2px solid var(--bottle)}
.topbar b{font:400 22px 'Rozha One','Hind',serif;color:var(--bottle)}.topbar small{margin-left:10px;color:var(--muted);font-size:14px}
.pill{display:inline-flex;align-items:center;gap:7px;background:var(--bottle);color:#fff;border-radius:999px;padding:5px 13px 5px 9px;font-size:13px;font-weight:600;white-space:nowrap}
.pill i{width:9px;height:9px;border-radius:50%;background:var(--haldi);box-shadow:0 0 0 0 #f1b32388;animation:pulse 2.4s infinite}
@keyframes pulse{70%{box-shadow:0 0 0 8px #f1b32300}100%{box-shadow:0 0 0 0 #f1b32300}}

/* overview hero: the day's ledger page */
.hero{display:grid;grid-template-columns:1.15fr 1fr;gap:28px;align-items:stretch;margin:6px 0 26px}
.hero-l{background:var(--bottle);color:#fff;border-radius:16px;padding:30px 32px;position:relative;overflow:hidden}
.hero-l::before{content:"";position:absolute;right:-40px;top:-40px;width:190px;height:190px;border-radius:50%;border:26px solid #14514a}
.hero-l small{color:#a9cbbd;font-size:14px;position:relative}
.hero-l h1{font:400 clamp(26px,3.2vw,40px)/1.25 'Rozha One','Hind',serif;color:#fff;margin:8px 0 0;position:relative;max-width:16ch}
.ledger{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 26px;box-shadow:0 10px 26px #0d3b3114;position:relative}
.ledger::before{content:"";position:absolute;left:44px;top:0;bottom:0;width:2px;background:#e6a7a0aa}
.lrow{display:flex;align-items:baseline;gap:8px;padding:13px 0 13px 40px;border-bottom:1px solid var(--rule);animation:inkin .6s both}
.lrow:nth-child(2){animation-delay:.12s}.lrow:nth-child(3){animation-delay:.24s}
.lrow span{color:var(--muted);font-size:15px}
.lrow em{flex:1;border-bottom:2px dotted #b8c7b5;transform:translateY(-4px)}
.lrow b{font-size:22px;font-variant-numeric:tabular-nums;color:var(--bottle)}
.lrow.total b{font-size:30px;padding-bottom:3px;border-bottom:3px double var(--bottle)}
.lrow:last-child{border-bottom:0}
@keyframes inkin{from{opacity:0;clip-path:inset(0 100% 0 0)}to{opacity:1;clip-path:inset(0 0 0 0)}}

/* metrics on other pages: ledger totals */
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--line);border-top:4px solid var(--bottle);padding:14px 18px;border-radius:12px;box-shadow:0 6px 18px #0d3b3110}
[data-testid="stMetricValue"]{color:var(--bottle);font-variant-numeric:tabular-nums;font-weight:700}
[data-testid="stMetricLabel"]{color:var(--muted)}

/* buttons */
div.stButton>button,div[data-testid="stDownloadButton"]>button,a[data-testid="stBaseLinkButton-secondary"],a[data-testid="stBaseLinkButton-primary"]{border-radius:10px;border:1.5px solid var(--bottle);background:#fff;color:var(--bottle);font-weight:600;min-height:44px;transition:transform .12s,box-shadow .12s,background .12s}
div.stButton>button:hover,div[data-testid="stDownloadButton"]>button:hover,a[data-testid^="stBaseLinkButton"]:hover{background:#eaf3ec;transform:translateY(-1px);box-shadow:0 6px 14px #0d3b3122;border-color:var(--bottle)}
div.stButton>button[kind="primary"],div[data-testid="stDownloadButton"]>button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stFormSubmitButton"]{background:var(--haldi);color:#2a1d00;border:0;font-weight:700}
button[data-testid="stBaseButton-primary"]:hover,button[data-testid="stBaseButton-primaryFormSubmit"]:hover{background:#ffc531;color:#2a1d00}
button[data-testid="stBaseButton-primaryFormSubmit"]{background:var(--haldi);color:#2a1d00;border:0;font-weight:700}
a[data-testid^="stBaseLinkButton"]{background:#25D366;border-color:#1da851;color:#06361a!important}
a[data-testid^="stBaseLinkButton"]:hover{background:#2fe173}
:focus-visible{outline:3px solid var(--haldi)!important;outline-offset:2px}

/* inputs */
[data-baseweb="input"],[data-baseweb="textarea"],[data-baseweb="select"]>div{border-radius:10px!important;background:#fff}
[data-baseweb="input"]:focus-within,[data-baseweb="textarea"]:focus-within{box-shadow:0 0 0 3px #f1b32366;border-color:var(--haldi-d)!important}
[data-testid="stForm"]{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;box-shadow:0 8px 22px #0d3b3110}
[data-testid="stVerticalBlockBorderWrapper"]:has(>div>[data-testid="stVerticalBlock"]>[data-testid="stElementContainer"] h4){border-radius:14px}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line)!important;background:var(--card);transition:box-shadow .15s,transform .15s}
[data-testid="stColumn"] [data-testid="stVerticalBlockBorderWrapper"]:hover{box-shadow:0 12px 26px #0d3b3118;transform:translateY(-2px)}
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}
[data-testid="stFileUploader"] section{background:var(--card);border:2px dashed #7d9a8c;border-radius:14px;transition:border-color .15s,background .15s}
[data-testid="stFileUploader"] section:hover{border-color:var(--haldi-d);background:#fffbea}
[data-testid="stAlert"]{border-radius:12px;border:1px solid var(--line)}
[data-testid="stExpander"]{border-radius:12px;border-color:var(--line);background:var(--card)}
hr{border-color:var(--bottle)!important;opacity:.25}

/* khata (udhaar) cards */
.udhaar{display:flex;align-items:center;gap:16px;background:var(--card);border:1px solid var(--line);border-left:6px solid var(--soon);border-radius:12px;padding:14px 18px;margin:14px 0 8px;box-shadow:0 5px 14px #0d3b3110}
.udhaar.late{border-left-color:var(--late)}.udhaar.today{border-left-color:var(--today)}
.udhaar .who{flex:1;min-width:0}.udhaar .who b{font-size:18px;color:var(--bottle)}.udhaar .who div{color:var(--muted);font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.udhaar .amt{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums;color:var(--ink)}
.chip{font-size:12.5px;font-weight:700;border-radius:999px;padding:4px 12px;background:#dff0e6;color:#1b5e40;white-space:nowrap}
.udhaar.late .chip{background:#f9dcd6;color:#8f2615}.udhaar.today .chip{background:#fdeec2;color:#7a5600}

/* stock cards */
.stockgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;margin:12px 0 18px}
.stk{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:0 5px 14px #0d3b3110}
.stk b{display:block;font-size:16px;color:var(--bottle);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.stk .q{font-size:28px;font-weight:700;font-variant-numeric:tabular-nums}.stk .q small{font-size:14px;color:var(--muted);font-weight:500;margin-left:4px}
.bar{height:8px;border-radius:5px;background:#e3ebe1;margin:8px 0 6px;overflow:hidden}.bar i{display:block;height:100%;border-radius:5px;background:var(--soon);transition:width .5s}
.stk.low .bar i{background:var(--late)}.stk.low .q{color:var(--late)}
.stk span{font-size:12.5px;color:var(--muted)}

@media(max-width:900px){.hero{grid-template-columns:1fr}.block-container{padding:.8rem .9rem 2.5rem}.topbar small{display:none}.udhaar{flex-wrap:wrap}.ledger::before{left:30px}.lrow{padding-left:30px}}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>""",unsafe_allow_html=True)
import html as _html
_DAYS_HI=["सोमवार","मंगलवार","बुधवार","गुरुवार","शुक्रवार","शनिवार","रविवार"]
def _day_label(d,lang): return (f"{_DAYS_HI[d.weekday()]}, {d.strftime('%d/%m/%Y')}" if lang!="English" else d.strftime("%A, %d %B %Y"))
def hero_html(greeting,day,rows):
    r="".join(f'<div class="lrow{" total" if tot else ""}"><span>{_html.escape(a)}</span><em></em><b>{_html.escape(b)}</b></div>' for a,b,tot in rows)
    return f'<div class="hero"><div class="hero-l"><small>{_html.escape(day)}</small><h1>{_html.escape(greeting)}</h1></div><div class="ledger">{r}</div></div>'
def udhaar_html(name,note,amount,due_label,state):
    return f'<div class="udhaar {state}"><div class="who"><b>{_html.escape(name)}</b><div>{_html.escape(note or "—")}</div></div><span class="chip">{_html.escape(due_label)}</span><span class="amt">₹{amount:,.2f}</span></div>'
def stock_html(items):
    out=""
    for i in items:
        thr=float(i["threshold"] or 0); q=float(i["quantity"]); low=q<=thr; pct=min(100,(q/(thr*3 if thr>0 else max(q,1)))*100)
        out+=f'<div class="stk{" low" if low else ""}"><b>{_html.escape(str(i["product"]))}</b><div class="q">{q:g}<small>{_html.escape(str(i["unit"]))}</small></div><div class="bar"><i style="width:{pct:.0f}%"></i></div><span>{"Low · alert at" if low else "Alert at"} {thr:g}</span></div>'
    return f'<div class="stockgrid">{out}</div>'
L={"English":{"nav":["Overview","Voice billing","Khata & reminders","Smart inventory","Monthly reports","Documents & analysis","Ledger","Invoice history"],"title":"Dukaan Digital","sub":"Your shop’s digital munim · Powered by Gemma 4","new":"Create a bill","draft":"Review your bill","confirm":"Confirm and issue invoice","upload":"Upload a bill, invoice, receipt, or ledger","review":"Review extracted information before saving","no_data":"No saved business data yet.","search":"Search invoices","lang":"Language","tax":"GST rate (%)","tax_type":"Tax treatment","customer":"Customer (optional)","record":"Save reviewed records","error":"Needs your review","recent":"Recent invoices","revenue":"Recorded invoice value","docs":"Documents processed","lines":"Review extracted rows","ledger":"Ledger entries","analyze":"Analyze document","english":"English","hindi":"हिन्दी"},"हिन्दी":{"nav":["डैशबोर्ड","आवाज़ से बिल","उधार और रिमाइंडर","स्मार्ट इन्वेंटरी","मासिक रिपोर्ट","दस्तावेज़ और विश्लेषण","बही-खाता","बिल इतिहास"],"title":"दुकान डिजिटल","sub":"आपकी दुकान का डिजिटल मुनीम · Gemma 4 द्वारा संचालित","new":"नया बिल बनाएं","draft":"बिल जांचें","confirm":"पुष्टि करें और बिल जारी करें","upload":"बिल, रसीद या बही-खाता अपलोड करें","review":"सहेजने से पहले निकली जानकारी जांचें","no_data":"अभी कोई व्यवसाय रिकॉर्ड सहेजा नहीं है।","search":"बिल खोजें","lang":"भाषा","tax":"GST दर (%)","tax_type":"कर का प्रकार","customer":"ग्राहक (वैकल्पिक)","record":"जांचे हुए रिकॉर्ड सहेजें","error":"जांच आवश्यक","recent":"हाल के बिल","revenue":"दर्ज बिल राशि","docs":"प्रसंस्कृत दस्तावेज़","lines":"निकली पंक्तियां जांचें","ledger":"बही-खाता प्रविष्टियां","analyze":"दस्तावेज़ विश्लेषण","english":"English","hindi":"हिन्दी"}}
TODAY=datetime.now(ZoneInfo("Asia/Kolkata")).date()
st.sidebar.markdown('<div class="sb-brand"><div class="sb-mark">मु</div><div><b>MunshiPro</b><span>Dukaan Digital · दुकान डिजिटल</span></div></div>',unsafe_allow_html=True)
if "lang" not in st.session_state: st.session_state.lang="English"
st.session_state.lang=st.sidebar.selectbox("Language / भाषा",["English","हिन्दी"],index=0 if st.session_state.lang=="English" else 1)
t=L[st.session_state.lang]; st.markdown(f'<div class="topbar"><div><b>{t["title"]}</b><small>{t["sub"]}</small></div><span class="pill"><i></i>Gemma 4</span></div>',unsafe_allow_html=True)
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
    st.markdown(hero_html(("Good day. Here’s your shop at a glance." if st.session_state.lang=="English" else "नमस्ते, आज आपकी दुकान का हाल।"),_day_label(TODAY,st.session_state.lang),[(t["recent"],str(len(invoices)),False),(t["revenue"],f"₹{sum(float(x['total']) for x in invoices):,.2f}",True),(t["docs"],str(len(db.documents())),False)]),unsafe_allow_html=True)
    st.subheader(t["recent"]); search=st.text_input(t["search"])
    rows=[i for i in invoices if search.casefold() in (i["number"]+i["customer"]).casefold()]
    if rows: st.dataframe(pd.DataFrame(rows)[["number","created","customer","status","total"]],use_container_width=True,hide_index=True)
    else:
        st.info(t["no_data"])
        a,b,c=st.columns(3)
        with a.container(border=True):
            st.markdown("#### 🎙️ Voice billing")
            st.caption("Create a reviewed invoice by speaking or typing an order.")
            if st.button("Create your first bill →",key="quick_bill"): st.session_state.quick_nav=t["nav"][1]
        with b.container(border=True):
            st.markdown("#### ▧ Upload records")
            st.caption("Bring in sales sheets, receipts, or ledger pages.")
            if st.button("Analyze a document →",key="quick_upload"): st.session_state.quick_nav=t["nav"][5]
        with c.container(border=True):
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
            st.markdown(udhaar_html(credit['customer'],credit['note'],float(credit['amount']),due_label,("late" if credit["due_date"]<TODAY.isoformat() else "today" if credit["due_date"]==TODAY.isoformat() else "soon")),unsafe_allow_html=True)
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
        st.markdown(stock_html(stock),unsafe_allow_html=True)
        with st.expander("Table view / तालिका"): st.dataframe(pd.DataFrame(stock)[["product","quantity","unit","threshold","supplier_phone"]],use_container_width=True,hide_index=True)
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
    IMG_EXT=(".png",".jpg",".jpeg",".webp",".tif",".tiff")
    def _has_gemini():
        if os.getenv("GEMINI_API_KEY"): return True
        try: return bool(st.secrets.get("GEMINI_API_KEY"))
        except Exception: return False
    def _num(v):
        try: return float(str(v).replace(",","").replace("₹","").strip() or 0)
        except Exception: return 0.0
    def _gemma_frame(rows):
        cols=["date","customer","description","debit","credit","confidence","reviewed"]
        return pd.DataFrame([{"date":str(r.get("date") or ""),"customer":str(r.get("customer") or ""),"description":str(r.get("description") or ""),"debit":_num(r.get("debit")),"credit":_num(r.get("credit")),"confidence":str(r.get("confidence") or "low").lower(),"reviewed":False} for r in rows if isinstance(r,dict)],columns=cols)
    def _read_with_gemma(docid,data,filename):
        with st.spinner("Reading the page with Gemma 4..."):
            st.session_state.gemma_ledger=(docid,read_ledger_image(data,mimetypes.guess_type(filename)[0] or "image/jpeg"))
    has_ai=_has_gemini()
    st.subheader(t["upload"]); uploaded=st.file_uploader(t["upload"],type=["csv","xlsx","xls","pdf","png","jpg","jpeg","webp","tif","tiff"])
    if uploaded and st.button(t["analyze"],type="primary"):
        try:
            raw=uploaded.getvalue(); is_img=Path(uploaded.name).suffix.lower() in IMG_EXT
            docid=db.add_document(file_hash(raw),uploaded.name,raw,"upload")
            if docid is None:
                row=db.db.execute("SELECT id FROM documents WHERE filename=? ORDER BY id DESC",(uploaded.name,)).fetchone()
                docid=row["id"] if row else None
                if docid is not None: st.info("This document was uploaded before, so it was reopened instead of being saved twice.")
            if docid is None: st.warning("This exact document was already uploaded; duplicate prevented.")
            elif is_img and has_ai:
                st.session_state.extracted=(docid,"text","",uploaded.name); st.session_state.pop("gemma_ledger",None)
                _read_with_gemma(docid,raw,uploaded.name)
            else:
                with st.spinner("Extracting text..."): content,kind=extract(uploaded)
                st.session_state.extracted=(docid,kind,content,uploaded.name)
        except Exception as e: st.error(f"Could not process this file: {e}")
    if st.session_state.get("extracted"):
        docid,kind,content,name=st.session_state.extracted;st.write("#### "+t["review"]);st.caption("Source retained: "+name)
        is_img=Path(name).suffix.lower() in IMG_EXT
        if kind=="text":
            if content.strip():
                st.text_area("Extracted original text",content,height=200,key=f"ocr_text_{docid}")
                is_ledger=st.checkbox("This is a handwritten ledger / यह हस्तलिखित बही है",key=f"is_ledger_{docid}")
                parsed=parse_ledger_text(st.session_state[f"ocr_text_{docid}"]) if is_ledger else []
                if parsed:
                    ed=st.data_editor(pd.DataFrame(parsed),num_rows="dynamic",use_container_width=True,hide_index=True,key=f"ocr_rows_{docid}")
                    if st.button(t["record"],key=f"ocr_save_{docid}"): db.add_entries(docid,ed.to_dict("records")); st.success("Reviewed entries saved")
                else: st.info("Text is preserved for verification. Tick the ledger box to turn it into rows, then correct them before saving.")
            if is_img:
                have=st.session_state.get("gemma_ledger",(None,))[0]==docid
                if has_ai:
                    if st.button("↻ Read again with Gemma 4" if have else "✨ Read handwritten page with Gemma 4 vision",key=f"gemma_ledger_{docid}"):
                        try:
                            src_row=db.db.execute("SELECT content FROM documents WHERE id=?",(docid,)).fetchone()
                            _read_with_gemma(docid,src_row["content"],name); have=True
                        except Exception as e: st.error(f"Gemma could not read this image: {e}")
                else: st.caption("Add GEMINI_API_KEY to enable Gemma 4 multimodal handwriting recognition.")
                if have:
                    st.markdown("#### Gemma 4 transcription · review every value")
                    frame=_gemma_frame(st.session_state.gemma_ledger[1])
                    if frame.empty:
                        st.warning("Gemma could not read this page automatically. Your photo is shown below: type the rows you can see into the table, or press Read again with a straighter, well-lit photo.")
                        frame=pd.DataFrame([{"date":"","customer":"","description":"","debit":0.0,"credit":0.0,"confidence":"low","reviewed":False} for _ in range(5)])
                    with st.expander("📷 View uploaded photo (compare while reviewing)",expanded=True):
                        _img=db.db.execute("SELECT content FROM documents WHERE id=?",(docid,)).fetchone()
                        if _img: st.image(bytes(_img["content"]),use_container_width=True)
                    gemma_edit=st.data_editor(frame,num_rows="dynamic",use_container_width=True,hide_index=True,key=f"gemma_rows_{docid}")
                    if st.button("Save reviewed Gemma rows",key=f"gemma_save_{docid}"): db.add_entries(docid,gemma_edit.to_dict("records")); st.success("Reviewed Gemma rows saved.")
        else:
            try:
                frame=normalize(content); st.dataframe(frame,use_container_width=True,hide_index=True)
                edited=st.data_editor(frame,num_rows="dynamic",use_container_width=True,hide_index=True,key=f"table_rows_{docid}")
                if st.button(t["record"],key=f"table_save_{docid}"):
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