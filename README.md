# UniEval — Multi-Agent Debate for Improving LLM Reasoning

An experimental workbench for the research question: **does multi-agent debate improve
LLM reasoning compared with a single LLM agent?** It deliberately stores intermediate
agent outputs so a student can inspect whether debate corrected an error or merely
added cost. Prompts request concise conclusions, evidence, and critiques rather than
private chain-of-thought.

## Architecture

```text
React/Vite UI
   |  /questions, /experiments/run, /experiments/compare
FastAPI routers -> experiment service -> configurable LLM provider
                                  -> SQLite (experiments + per-question outputs)
```

The backend is organized under `backend/app`: `llm.py` contains the provider adapter
(mock or OpenAI-compatible), `dataset.py` contains 25 labeled questions, `db.py`
contains persistence, and `routers/experiments.py` runs the single/debate pipelines.
The frontend is a small Vite app in `frontend/src`.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The default `LLM_PROVIDER=mock` is deterministic and needs
no API key, making the project runnable for demonstrations and UI development. To use
any OpenAI-compatible endpoint, copy `.env.example` to `.env`, set
`LLM_PROVIDER=openai`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`.

## API

`GET /health`, `GET /questions`, `GET /experiments`, `GET /experiments/{id}`,
`POST /experiments/run`, and `POST /experiments/compare` are available. A run accepts
`mode` (`single` or `debate`), `rounds` (1–5), `model`, `question`, and optional
`question_ids`. `/compare` runs both methods on the same dataset and calculates
accuracy change, time change, call change, and token change. Every output includes
execution time, LLM calls, token usage, category, final answer, correctness, and
agent transcripts. Objective correctness is normalized reference matching; it is a
transparent baseline, not a substitute for human evaluation.

## Experimental methodology

Use `Run paired comparison` for a controlled run over all 25 questions. Keep model,
temperature, dataset, and question order fixed; change only the method and debate
round count. Report accuracy and error cases alongside average time, calls, and
tokens. The mock provider is useful for wiring validation but is not evidence about
LLM quality. For a report, repeat runs with a real provider, save the returned JSON,
and separately sample outputs for human or LLM-as-a-judge assessment.

## Example result

```json
{"mode":"debate","metrics":{"accuracy":100.0,"avg_time_ms":12.4,"avg_llm_calls":4.0,"avg_tokens":39.0},"comparison":{"accuracy_change_percentage_points":4.0,"call_change_percentage":300.0}}
```
