import sqlite3, json
from pathlib import Path
from datetime import datetime

class Store:
    def __init__(self,path="dukaan.sqlite3"):
        self.path=Path(path); self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, number TEXT UNIQUE, created TEXT, customer TEXT, status TEXT, subtotal TEXT, discount TEXT, tax TEXT, total TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, digest TEXT UNIQUE, filename TEXT, content BLOB, created TEXT, kind TEXT);
        CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY, document_id INTEGER, created TEXT, payload TEXT, reviewed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS credits(id INTEGER PRIMARY KEY, customer TEXT NOT NULL, phone TEXT NOT NULL, amount TEXT NOT NULL, due_date TEXT NOT NULL, note TEXT DEFAULT '', upi_id TEXT DEFAULT '', status TEXT DEFAULT 'pending', created TEXT NOT NULL, paid_at TEXT);
        CREATE TABLE IF NOT EXISTS inventory(id INTEGER PRIMARY KEY, product TEXT NOT NULL COLLATE NOCASE UNIQUE, quantity REAL NOT NULL DEFAULT 0, threshold REAL NOT NULL DEFAULT 3, unit TEXT DEFAULT 'pcs', supplier_phone TEXT DEFAULT '', supplier_message TEXT DEFAULT 'Namaste, please send {quantity} {unit} of {product}.');
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY, created TEXT NOT NULL, customer TEXT DEFAULT '', amount TEXT NOT NULL, tax TEXT NOT NULL DEFAULT '0', payment_mode TEXT NOT NULL DEFAULT 'Cash', invoice_number TEXT DEFAULT '', payload TEXT DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS reminder_log(id INTEGER PRIMARY KEY, credit_id INTEGER NOT NULL, sent_at TEXT NOT NULL, provider TEXT NOT NULL, message_id TEXT DEFAULT '', UNIQUE(credit_id, sent_at));
        """)
        self.db.execute("INSERT INTO sales(created,customer,amount,tax,payment_mode,invoice_number,payload) SELECT i.created,i.customer,i.total,i.tax,'Unclassified',i.number,i.payload FROM invoices i WHERE NOT EXISTS (SELECT 1 FROM sales s WHERE s.invoice_number=i.number)")
        self.db.commit()
    def invoices(self): return [dict(r) for r in self.db.execute("SELECT * FROM invoices ORDER BY id DESC")]
    def add_invoice(self,customer,items,totals,payment_mode="Cash"):
        now=datetime.now().astimezone().isoformat(timespec="seconds"); n=self.db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]+1
        number=f"DD-{datetime.now():%y%m%d}-{n:04d}"
        self.db.execute("INSERT INTO invoices(number,created,customer,status,subtotal,discount,tax,total,payload) VALUES(?,?,?,?,?,?,?,?,?)",(number,now,customer,"issued",str(totals["subtotal"]),str(totals["discount"]),str(totals["tax"]),str(totals["total"]),json.dumps(items,ensure_ascii=False)))
        self.db.execute("INSERT INTO sales(created,customer,amount,tax,payment_mode,invoice_number,payload) VALUES(?,?,?,?,?,?,?)",(now,customer,str(totals["total"]),str(totals["tax"]),payment_mode,number,json.dumps(items,ensure_ascii=False)))
        for item in items:
            product=str(item.get("product","")).strip()
            if product: self.db.execute("UPDATE inventory SET quantity=quantity-? WHERE product=?",(float(item.get("quantity",0) or 0),product))
        self.db.commit(); return number
    def sales(self): return [dict(r) for r in self.db.execute("SELECT * FROM sales ORDER BY id DESC")]
    def add_credit(self,customer,phone,amount,due_date,note="",upi_id=""):
        self.db.execute("INSERT INTO credits(customer,phone,amount,due_date,note,upi_id,created) VALUES(?,?,?,?,?,?,?)",(customer.strip(),phone.strip(),str(amount),str(due_date),note.strip(),upi_id.strip(),datetime.now().astimezone().isoformat(timespec="seconds"))); self.db.commit()
    def credits(self,include_paid=False):
        q="SELECT * FROM credits"+("" if include_paid else " WHERE status='pending'")+" ORDER BY due_date,id"
        return [dict(r) for r in self.db.execute(q)]
    def settle_credit(self,credit_id): self.db.execute("UPDATE credits SET status='paid',paid_at=? WHERE id=?",(datetime.now().astimezone().isoformat(timespec="seconds"),credit_id)); self.db.commit()
    def upsert_stock(self,product,quantity,threshold,unit="pcs",supplier_phone="",supplier_message=""):
        self.db.execute("INSERT INTO inventory(product,quantity,threshold,unit,supplier_phone,supplier_message) VALUES(?,?,?,?,?,?) ON CONFLICT(product) DO UPDATE SET quantity=excluded.quantity,threshold=excluded.threshold,unit=excluded.unit,supplier_phone=excluded.supplier_phone,supplier_message=excluded.supplier_message",(product.strip(),float(quantity),float(threshold),unit,supplier_phone.strip(),supplier_message or "Namaste, please send {quantity} {unit} of {product}.")); self.db.commit()
    def inventory(self): return [dict(r) for r in self.db.execute("SELECT * FROM inventory ORDER BY product COLLATE NOCASE")]
    def reminder_logged(self,credit_id): return self.db.execute("SELECT 1 FROM reminder_log WHERE credit_id=?",(credit_id,)).fetchone() is not None
    def log_reminder(self,credit_id,provider,message_id=""):
        now=datetime.now().astimezone().isoformat(timespec="seconds"); self.db.execute("INSERT OR IGNORE INTO reminder_log(credit_id,sent_at,provider,message_id) VALUES(?,?,?,?)",(credit_id,now,provider,message_id)); self.db.commit()
    def add_document(self,digest,filename,content,kind):
        cur=self.db.execute("INSERT OR IGNORE INTO documents(digest,filename,content,created,kind) VALUES(?,?,?,?,?)",(digest,filename,content,datetime.now().isoformat(timespec="seconds"),kind)); self.db.commit()
        if cur.rowcount==0: return None
        return cur.lastrowid
    def add_entries(self,document_id,rows):
        self.db.executemany("INSERT INTO entries(document_id,created,payload) VALUES(?,?,?)",[(document_id,datetime.now().isoformat(),json.dumps(r,ensure_ascii=False)) for r in rows]);self.db.commit()
    def documents(self): return [dict(r) for r in self.db.execute("SELECT id,filename,created,kind FROM documents ORDER BY id DESC")]
