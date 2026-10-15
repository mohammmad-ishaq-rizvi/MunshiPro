# MunshiPro · Dukaan Digital

A Hindi-first digital munim for kirana shops, repair stalls, and independent sellers. Capture sales by voice, read ledger photos as editable rows, track udhaar and stock, and share a shop summary with an accountant.

## Features

- **Gemma 4 assistant:** parses Hindi, Hinglish, and English voice transcripts into editable bill drafts and reads handwritten ledger photographs using image understanding. AI suggestions are never saved as verified records without review.
- **Udhaar reminders:** record customer, WhatsApp number, balance, due date, and UPI ID. Create a one-tap personalized WhatsApp nudge or optionally send an approved template automatically on/after the due date.
- **Smart inventory:** set stock counts and thresholds. Issued invoices reduce matching products; low stock shows a reorder alert and a prefilled wholesaler WhatsApp message.
- **Weekly/monthly PDF summary:** recorded sales, UPI and cash breakdown, open credits, and tax recorded on invoices. Download the report or send it through an approved WhatsApp document template.
- **Bilingual navigation**, local SQLite bookkeeping, invoice history, image/PDF/spreadsheet review, CSV export, and duplicate-upload detection.

## Run locally

Use Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, usually http://localhost:8501. Core bookkeeping works without API credentials. Image OCR needs Tesseract with English and Hindi language packs; the Docker image installs them.

## Gemma 4 setup

Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey), then set `GEMINI_API_KEY`. The default model is `gemma-4-26b-a4b-it`; set `GEMMA_MODEL` to change it. In the app, select **Parse with Gemma 4** for a voice transcript or **Read handwritten page with Gemma 4 vision** for a ledger photo. The selected transcript or image is sent to Google’s Gemini API. See Google’s [Gemma Gemini API guide](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api).

## WhatsApp setup

Manual reminders use a prefilled `wa.me` link. Automatic due reminders require Meta WhatsApp Cloud API credentials and an approved utility template with four body parameters: customer name, amount, due date, and UPI URI. Configure `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `META_GRAPH_VERSION`, `WHATSAPP_TEMPLATE_NAME`, and optionally `WHATSAPP_TEMPLATE_LANGUAGE`. The single app instance checks daily at 9:00 AM India time.

Direct PDF delivery needs another approved template with a **document header** and four body parameters: period, sales, open credit, and recorded GST. Set `WHATSAPP_SUMMARY_TEMPLATE_NAME` and optionally `WHATSAPP_SUMMARY_TEMPLATE_LANGUAGE`. The shop owner enters the recipient number in Reports.

Copy `.env.example` to `.env` for Docker Compose settings. Keep real API keys private.

## Deploy

### Render

Push this folder to a Git repository you control, then create a Render Blueprint from `render.yaml`. It provisions a Docker web service with persistent storage at `/data`. Add optional Gemma/WhatsApp credentials in the service environment. Back up `/data/dukaan.sqlite3`. Render persistent disks require a paid plan; review provider pricing and region options before deployment.

### Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Open http://localhost:8501. SQLite is kept in the named `munshi-data` volume.

## Data and limitations

SQLite defaults to `dukaan.sqlite3` beside the app; set `DUKAAN_DB_PATH` for persistent host storage. This is a single-shop starter without merchant authentication, tenant isolation, or an encrypted database. Add suitable access controls, backups, and retention policies before using a public instance for real customer data.

GST figures use only the rates entered by the merchant; the app does not determine taxability, HSN, place of supply, exemptions, filing liability, or statutory compliance. AI, OCR, and speech recognition can misread values; review every extracted field. Stock only adjusts for products already in inventory with matching names.

See [LICENSE](LICENSE).
