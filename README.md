# NetSage AI

NetSage AI is a local, educational Cisco network-troubleshooting assistant. It combines deterministic Python checks with a Groq-hosted language model, saves structured diagnoses, evaluates them against case-specific expectations, and records human review decisions.

## Features

- 41 structured Cisco troubleshooting cases
- Explainable rule checks for routing, VLAN, DHCP, DNS, ACL, NAT, wireless, and interface issues
- Strict JSON-schema AI diagnoses with confidence, evidence, next command, and ordered fix steps
- Streamlit dashboard for case analysis and human review
- Deterministic evaluation of AI root-cause agreement
- CSV-based audit trail for diagnoses, evaluations, and reviews

## Technology Stack

- Python 3.10+
- Streamlit and pandas for the dashboard
- Groq Python SDK for optional AI analysis
- Pydantic for response validation
- CSV and JSON files for local persistence

## Project Structure

```text
checker/                  Application and CLI modules
  checker.py              Deterministic rule checker
  dashboard.py            Streamlit dashboard
  evaluate.py             Diagnosis evaluator
  netsage.py              Groq orchestration and persistence
  review.py               CLI human-review workflow
  test_groq.py            Explicit Groq schema smoke test
data/cases.csv             Troubleshooting case dataset
prompts/diagnose_prompt.md Prompt specification and examples
results/                   Sample diagnoses and evaluation output
packet_tracer/             Optional local Packet Tracer files
reports/                   Local project reports, ignored by Git
```

The nested `NetSage_AI/` directory is a duplicate local export and is ignored by Git. The repository root is the canonical application tree.

## Installation

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and set `GROQ_API_KEY` to a newly issued key for the account being used. The application loads this local file through `python-dotenv`; `.env` is ignored and must never be committed.

AI analysis requires the key. Browsing cases, running deterministic checks, and viewing existing local results do not require an API call.

## Run Locally

Start the dashboard:

```powershell
python -m streamlit run checker/dashboard.py
```

Run the CLI for one case, several cases, or all cases:

```powershell
python checker/netsage.py --case 001
python checker/netsage.py --case 001,015,023 --rerun
python checker/netsage.py --all
```

View a saved diagnosis without calling Groq:

```powershell
python checker/netsage.py --view 001
```

Run deterministic evaluation and the optional human-review CLI:

```powershell
python checker/evaluate.py
python checker/review.py --case 001
```

The `checker/test_groq.py` script makes a real API request and is intentionally opt-in:

```powershell
python checker/test_groq.py
```

## Testing

The repository currently has no automated test suite. At minimum, run the deterministic checker, evaluator, Python compilation, and the dashboard smoke check after installation:

```powershell
python -m compileall checker
python checker/checker.py
python checker/evaluate.py
python -m streamlit run checker/dashboard.py
```

The dashboard and CLI write local result files under `results/`. Review logs and backups are ignored because they may contain local or personal information.

## Security Notes

- Never commit `.env`, API keys, credentials, or private network exports.
- Rotate any credential that has been shared outside its intended secret store.
- NetSage AI does not authenticate dashboard users and is intended for local educational use.
- AI output is advisory. Human review is required before applying any network change.
- The application does not autonomously configure network devices.

## API Information

AI diagnosis uses the Groq Chat Completions API with the `openai/gpt-oss-120b` model and a strict JSON response schema. The API key is read only from `GROQ_API_KEY`.

## Future Improvements

- Add automated unit tests for checker and evaluator rules.
- Add authenticated deployment support before exposing the dashboard beyond localhost.
- Add structured storage and retention controls for diagnosis and review records.
- Add dependency vulnerability scanning and CI checks.