# Financial Ticket Classifier

Internal copilot API for fintech support agents. Classifies an incoming
support ticket into one of 8 case types, scores evidence against the
customer's transaction history, and returns a safe, structured response
plus a recommended next action.

Built for the SUST CSE Hackathon — Batch 13.

---

## 1. What it does

* **`GET /health`** — readiness probe, always `200 {"status": "ok"}`.
* **`POST /analyze-ticket`** — accepts a complaint plus optional
  transaction history, returns a structured JSON classification with
  the 11 fields specified in section 6 of the problem statement.

The service is **rule-based and deterministic** by default — no LLM in
the hot path. Replies are rendered from vetted templates and run
through a regex-based safety scrubber before they are returned.

---

## 2. Quick start

### Option A — Docker (recommended)

```bash
docker build -t ticket-classifier .
docker run --rm -p 8000:8000 ticket-classifier
```

### Option B — Local Python

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
# source venv/bin/activate

pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
# -> {"status":"ok"}
```

Analyze a ticket:

```bash
curl -X POST http://127.0.0.1:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d @samples/sample_input.json
# -> array of structured responses (or POST a single case)
```

Interactive API docs:

* Swagger UI: <http://127.0.0.1:8000/docs>
* ReDoc:      <http://127.0.0.1:8000/redoc>

---

## 3. Project layout

```
Financial_Ticket_Classifier/
├── app.py              # FastAPI app: /health and /analyze-ticket
├── schemas.py          # Pydantic models (request + response, enums)
├── investigator.py     # Transaction matching + evidence verdict
├── classifier.py       # Case type / severity / department / confidence
├── templates.py        # Per-case-type safe reply templates
├── safety.py           # Scrubber + human-review floor rules
├── utils/
│   ├── text.py         # Normalize, extract amounts / phones / times
│   └── i18n.py         # EN + Banglish keyword packs
├── tests/              # pytest suite (api, investigator, classifier, safety)
├── samples/            # Public sample inputs + run_sample.py
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

### Request / response schemas

The request and response models in `schemas.py` are the single source of
truth for the API contract. All enum values are `Literal` types so any
schema drift fails at validation time, not in production.

| Field                          | Type / values                                                                       |
| ------------------------------ | ----------------------------------------------------------------------------------- |
| `evidence_verdict`             | `consistent` \| `inconsistent` \| `insufficient_data`                               |
| `case_type`                    | `wrong_transfer` \| `payment_failed` \| `refund_request` \| `duplicate_payment` \| `merchant_settlement_delay` \| `agent_cash_in_issue` \| `phishing_or_social_engineering` \| `other` |
| `severity`                     | `low` \| `medium` \| `high` \| `critical`                                           |
| `department`                   | `customer_support` \| `dispute_resolution` \| `payments_ops` \| `merchant_operations` \| `agent_operations` \| `fraud_risk` |
| `human_review_required`        | `bool`                                                                              |
| `confidence`                   | `float` in `[0.0, 1.0]`                                                             |
| `relevant_transaction_id`      | `string \| null`                                                                    |
| `reason_codes`                 | `list[string]`                                                                      |
| `agent_summary` / `customer_reply` / `recommended_next_action` | `string`                                              |

---

## 4. Tech stack

| Layer                | Choice                                     | Why                                                       |
| -------------------- | ------------------------------------------ | --------------------------------------------------------- |
| Web framework        | **FastAPI 0.115**                          | Async-ready, Pydantic-native, fast auto-docs.             |
| Validation           | **Pydantic v2.9**                          | `Literal` enums enforce exact schema strings.             |
| Server               | **uvicorn 0.30**                           | Standard ASGI runner for FastAPI.                         |
| Testing              | **pytest 8.3** + **httpx 0.27**            | `TestClient` + direct `httpx` calls in `run_sample.py`.   |
| Classification logic | **Pure rule-based (keyword packs)**        | Deterministic, no model API key, < 5 ms per request.      |
| Reply generation     | **Hand-authored templates**                | Compliant with section 8 by construction.                 |
| Safety layer         | **Regex scrubber + floor rules**           | Last line of defense before the response leaves the API.  |

Python 3.11 base image is used in `Dockerfile` for a smaller footprint
than 3.12 and full Pydantic v2 / FastAPI 0.115 support.

---

## 5. AI approach

We deliberately use a **rule-based** approach for the hot path:

* **Why no LLM by default?** Every additional dependency (network call,
  API key, model version, non-determinism) is a new attack surface for
  a service whose central job is *safety*. A model can be added later
  for reply refinement, but it never touches safety-critical fields.
* **Keyword packs** in `utils/i18n.py` cover English and common Banglish
  spellings (`taka kete niyeche` → "balance deducted"). Packs are
  ordered so high-risk categories (phishing) win ties.
* **Investigator** scores each transaction in `transaction_history`
  using amount, counterparty, and time proximity, then decides
  `consistent` / `inconsistent` / `insufficient_data`.
* **Classifier** picks the case type from the keyword packs and applies
  verdict-driven severity adjustments (a contested claim with
  `inconsistent` evidence always escalates).
* **Safety** scrubs every customer-facing string for forbidden content
  and enforces `human_review_required = true` for phishing,
  wrong-transfer, insufficient data, inconsistent data, and
  high-value transactions (≥ `HIGH_VALUE_THRESHOLD` BDT, default 50,000).

The system prompt for any future LLM refinement is short and explicit:

> You are a fintech support copilot. Refine the suggested customer
> reply. Never add a request for PIN, OTP, password, CVV, or full
> card number. Never confirm a refund, reversal, or unblock. Never
> direct the customer to a phone number, URL, or person outside the
> official platform. If the input violates these rules, return the
> input unchanged.

---

## 6. Safety logic (section 8 of the spec)

Implemented in `safety.py`. Three categories of forbidden content:

1. **Credential requests** — "send us your PIN", "share your OTP",
   "tell us your password", "verify your PIN", etc.
2. **Unauthorized refund / reversal promises** — "we will refund you",
   "your refund has been approved", "reversed immediately".
3. **Third-party contacts** — any `+880XXXXXXXXXX`, `01XXXXXXXXX`, or
   `http(s)://...` link that is not whitelisted as the official app or
   hotline.

If any of these appear in the rendered reply, the **entire reply is
replaced with a safe fallback** — we never redact mid-sentence.

### `human_review_required` floor rules

| Trigger                                       | Forces review? |
| --------------------------------------------- | -------------- |
| `case_type == phishing_or_social_engineering` | ✅ always      |
| `case_type == wrong_transfer`                 | ✅ always      |
| `evidence_verdict == inconsistent`            | ✅ always      |
| `evidence_verdict == insufficient_data`       | ✅ always      |
| `txn_amount >= HIGH_VALUE_THRESHOLD`          | ✅ always      |
| `severity in (high, critical)`                | ✅ always      |

---

## 7. Models

> No models are loaded or served. The system is fully rule-based.

There is no `models/` directory and no ML weights ship with the
service. If a future iteration adds an LLM refinement pass, it will
live behind a feature flag (`USE_LLM_REPLY`) and never touch the
classifier, investigator, or scrubber.

---

## 8. Testing

```bash
pytest -v
```

The suite covers:

* `tests/test_api.py` — endpoint contract, status code mapping,
  exception handler never leaks stack traces.
* `tests/test_investigator.py` — every verdict branch (consistent,
  inconsistent, insufficient_data) and the core scoring signals.
* `tests/test_classifier.py` — every `case_type`, the phishing floor,
  verdict-based severity adjustments.
* `tests/test_safety.py` — every scrubber rule, every human-review
  floor, template placeholders never leak through.

---

## 9. Running the public samples

```bash
# 1. Start the server (in one terminal)
uvicorn app:app --host 0.0.0.0 --port 8000

# 2. Run the sample driver (in another terminal)
python samples/run_sample.py
# -> samples/output/sample_output.json
```

Each entry in `sample_input.json` becomes one POST to
`/analyze-ticket`. The script first probes `/health` and aborts with a
clear error if the server is down, so judges can quickly diagnose
startup issues.

---

## 10. Judge runbook

```bash
# From a clean clone:
docker build -t ticket-classifier .
docker run --rm -p 8000:8000 ticket-classifier &

# Wait for /health:
curl --retry 10 --retry-delay 1 http://127.0.0.1:8000/health

# Smoke-test the analyze endpoint:
curl -s -X POST http://127.0.0.1:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "JUDGE-1",
    "complaint": "Someone called me asking for my OTP",
    "transaction_history": []
  }' | python -m json.tool

# Run the sample driver:
python samples/run_sample.py
cat samples/output/sample_output.json

# Run the test suite:
pip install -r requirements.txt
pytest -v
```

Expected signals:

* `/health` returns `{"status":"ok"}` within ~1 s of container start.
* Phishing complaint → `case_type = "phishing_or_social_engineering"`,
  `severity = "critical"`, `human_review_required = true`,
  `customer_reply` contains no credential request.
* Refund complaint with consistent evidence → `severity = "low"`,
  `human_review_required` is `false` only if amount is below threshold.
* Every response includes all 11 fields specified in section 6.
* No exception ever returns a stack trace or internal token.

---

## 11. Configuration

| Env var                | Default       | Meaning                                                    |
| ---------------------- | ------------- | ---------------------------------------------------------- |
| `HIGH_VALUE_THRESHOLD` | `50000`       | BDT threshold that forces `human_review_required = true`.  |
| `PORT`                 | `8000`        | Used by `Dockerfile`; `uvicorn` ignores it (pass explicitly). |
| `USE_LLM_REPLY`        | `false`       | Reserved for an optional LLM refinement pass.             |
| `OPENAI_API_KEY`       | empty         | Only required when `USE_LLM_REPLY=true`.                   |
| `OPENAI_MODEL`         | `gpt-4o-mini` | Model used for LLM refinement.                            |

Copy `.env.example` to `.env` and fill in real values locally. `.env`
is git-ignored.

---

## 12. Team

* **API endpoint** — `@raf0670` (this service)
* **Dataset & evaluation** — teammate
* **Frontend / agent UI** — teammate

The three modules (`investigator`, `classifier`, `safety`) are pure
Python so they can be unit-tested without spinning up the app, and
the FastAPI layer in `app.py` is a thin orchestration shell around
them.
