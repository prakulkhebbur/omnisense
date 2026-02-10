# OmniSense

> Real-time call analysis, orchestration, and operator dashboard.

OmniSense is a modular project for processing and managing live call streams, performing speech-to-text, ranking and severity scoring, and providing a web dashboard and API for operators.

## Key Features
- Real-time audio streaming and transcription (STT)
- Call orchestration and queue management
- Pattern detection and severity scoring
- Web dashboard for operators and callers

## Requirements
- Python 3.10+
- A virtual environment (recommended)
- Dependencies listed in [requirements.txt](requirements.txt)

## Installation
1. Create and activate a virtual environment:

Windows (PowerShell):
```powershell
python -m venv .venv
& .venv\Scripts\Activate.ps1
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Quickstart (development)
1. Start the API (example using uvicorn):
```bash
pip install uvicorn
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

2. Open the operator dashboard or static pages in a browser from the `static/` folder (for local testing you can open `static/index.html`). See [static/index.html](static/index.html).

3. To run example scripts or integration helpers, check `master_run.py` and the `scripts/` folder.

## Project Structure (high level)
- `src/api/` — API server and routes ([src/api/main.py](src/api/main.py))
- `src/core/` — orchestration and queue management ([src/core/orchestrator.py](src/core/orchestrator.py))
- `src/handlers/` — call handlers and integration logic
- `src/models/` — domain models (calls, operators, enums)
- `src/stt/` — speech-to-text implementations ([src/stt/speech_to_text.py](src/stt/speech_to_text.py))
- `src/services/` — services such as pattern detection
- `src/ranking/` — ranking and severity scoring logic
- `static/` — front-end pages and dashboard assets
- `scripts/` — helper scripts and tests (e.g., `scripts/test_api.py`)

## Development
- Follow the installation steps above.
- Use `uvicorn` for local API development.
- Tests and small integration scripts live under `scripts/`.

## Running Tests
If you have pytest installed, try:
```bash
pytest -q
# or run a specific script:
python scripts/test_api.py
```

## Contributing
Please open issues or pull requests. Follow standard Python packaging and test practices.

## License
This project does not include a license file by default. Consider adding a license such as MIT if you intend to publish.

## Contact
For questions, check the codebase or open an issue in this repository.
# omnisense