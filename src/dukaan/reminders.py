"""Optional scheduled WhatsApp Cloud API delivery for due khata reminders."""
import json,os
from datetime import datetime
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from zoneinfo import ZoneInfo
from .store import Store

def send_due_reminders(db):
    token=os.getenv("WHATSAPP_ACCESS_TOKEN"); phone_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID"); version=os.getenv("META_GRAPH_VERSION"); template=os.getenv("WHATSAPP_TEMPLATE_NAME")
    if not all((token,phone_id,version,template)): return 0
    today=datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(); sent=0
    for credit in db.credits():
        if credit["due_date"]>today or db.reminder_logged(credit["id"]): continue
        upi=credit.get("upi_id"); payment=f"upi://pay?pa={upi}&pn={credit['customer']}&am={credit['amount']}&cu=INR" if upi else "No UPI link saved; please contact the shop to pay."
        params=[credit["customer"],f"₹{float(credit['amount']):,.2f}",credit["due_date"],payment]
        body={"messaging_product":"whatsapp","to":"91"+"".join(c for c in credit["phone"] if c.isdigit())[-10:],"type":"template","template":{"name":template,"language":{"code":os.getenv("WHATSAPP_TEMPLATE_LANGUAGE","en_IN")},"components":[{"type":"body","parameters":[{"type":"text","text":p} for p in params]}]}}
        req=Request(f"https://graph.facebook.com/{version}/{phone_id}/messages",data=json.dumps(body).encode(),headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},method="POST")
        try:
            with urlopen(req,timeout=20) as response: result=json.loads(response.read().decode())
            message_id=(result.get("messages") or [{}])[0].get("id",""); db.log_reminder(credit["id"],"whatsapp-cloud",message_id); sent+=1
        except (HTTPError,URLError,TimeoutError,ValueError) as exc: print(f"WhatsApp reminder for credit {credit['id']} failed: {exc}")
    return sent

def run_scheduler(db_path):
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler=BackgroundScheduler(timezone=ZoneInfo("Asia/Kolkata"))
    scheduler.add_job(lambda:send_due_reminders(Store(Path(db_path))),"cron",hour=9,minute=0,id="khata-reminders",replace_existing=True,max_instances=1)
    scheduler.start(); return scheduler
