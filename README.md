# AI-Powered Student Feedback Agent

Upload or enter exam marks, get a calculated performance analysis, charts, a prioritised improvement plan with
learning resources (Tavily), an AI-written report, and a chatbot that answers questions about *your* results.

All numbers come from **Pandas/NumPy**, never from the LLM. The LLM (optional) interprets the calculated results,
writes advice, and chats; every AI-written part is labelled as such. Without any API keys the app still works:
reports use standard templates, the chatbot uses built-in rules, and resource search is skipped with a message.

## Features
- Student profile with extensible **board configuration** (AKU-EB, Cambridge, FBISE, Punjab, Sindh, Other). Boards do
  not share a grading scale; where a board has no fixed percentage-to-grade table, computed grades are marked *indicative*
  and a grade printed on the marksheet always wins.
- Marks entry by table, or upload of **CSV, Excel, PDF, PNG/JPG** (OCR optional). Extracted rows are always shown for
  review and correction before saving; missing or invalid marks are reported, never invented.
- Data cleaning and validation (missing values, duplicates, obtained > total, non-numeric, summary rows, subject aliases).
- Weakness/strength detection with **explained thresholds** (absolute, board pass mark, relative to own average, decline,
  inconsistency, shortfall against target). Previous-vs-current comparison and trends (3+ exams).
- Adaptive practice quizzes for weak subjects, with a student-described topic, custom question count, MCQ or Q/A formats,
  rendered Markdown/LaTeX, topic-level mastery, recency-weighted evidence, and flagged-question exclusion. Mastery
  verdicts require at least 8 answered questions across 2 completed quiz sessions by default.
- 9 charts (Matplotlib/Seaborn PNGs + interactive Plotly); charts that the data cannot support honestly are skipped with a reason.
- Four-stage agent workflow (analyst -> advisor -> resource researcher -> report generator) coordinated by a deterministic orchestrator.
- 13 LangChain tools over the analysis engine; the engine itself has no LangChain dependency.
- Improvement roadmap with task tracking, and a per-student chatbot with history.
- Data analysis toolkit with distribution shape, z-scores, consistency, outliers, correlations, moving averages,
  bootstrap change intervals, trend extrapolation, marks-lost Pareto analysis, target planning, weighted scores,
  safe pivots and Excel/CSV exports.

## Architecture
```
Streamlit  --HTTP-->  FastAPI  -->  services  -->  data_engine (Pandas/NumPy)  [no LLM, no web framework]
                                        |                |
                                        |                +--> visualizations (Matplotlib/Seaborn)
                                        +--> agents/orchestrator --> analyst -> advisor -> researcher(Tavily) -> report
                                        +--> chatbot (LangChain tools | rule-based fallback)
                                        +--> SQLAlchemy / SQLite
```
- `app/data_engine/analyzer.py` (`StudentAnalyzer`) holds the analysis operations; `app/agents/tools.py` wraps them as tools,
  including `get_topic_mastery`.
- Agents use `bind_tools` + `with_structured_output` from langchain-core (no deprecated `AgentExecutor`). Each LLM step
  falls back to a deterministic version on failure, and the report records a note.
- A report is only generated if stored data passes validation (otherwise HTTP 422 before any agent runs).
- Chat context is rebuilt from the database for the requesting student on every call, so students never mix.
- Uploaded files are deleted after extraction unless `KEEP_UPLOADED_FILES=true`.

## Setup (Windows PowerShell; macOS/Linux use `source venv/bin/activate`)
```powershell
uv venv .venv
uv pip install -r requirements.txt --python .venv\Scripts\python.exe
copy .env.example .env      # then edit .env
```
`.env` keys: `OPENROUTER_API_KEY` (optional; create one at openrouter.ai/keys) and `LLM_MODEL` (any OpenRouter model that supports
tool calling, e.g. `openai/gpt-4o-mini` or `anthropic/claude-3.5-sonnet`),
`TAVILY_API_KEY` (optional), plus storage paths. The database tables are created automatically on backend start.

Optional OCR for scanned marksheets: install the Tesseract program (Windows installer from the UB Mannheim build, and add it
to PATH) in addition to `pytesseract`. Without it, PDFs with a text layer and CSV/Excel still work.

## Run
```powershell
# Terminal 1
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
# Terminal 2
.venv\Scripts\python.exe -m streamlit run frontend/streamlit_app.py
# or both at once
.venv\Scripts\python.exe run.py
```
API docs: http://127.0.0.1:8000/docs - Frontend: http://localhost:8501

Try it: create a student, then on **Marks** upload `sample_data/sample_marksheet.csv` (3 exams, 7 subjects), save, and open the dashboard.

CSV/Excel layout: one row per subject per exam with columns `subject, obtained, total` (optional `exam, exam_type, grade`).
Excel files with several sheets use the sheet names as exam names when there is no `exam` column.

## Tests
```powershell
.venv\Scripts\python.exe -m pytest -v
```
No test needs an API key or network access.

## API
`GET /health/`, `GET /boards/`, `POST|GET /students/`, `GET|DELETE /students/{id}/`, `POST /students/{id}/marksheets/upload`,
`POST|GET /students/{id}/results/`, `GET /students/{id}/performance/ | weaknesses/ | visualizations/ | visualizations/{chart_id}/`,
`POST /students/{id}/analyze/`, `GET /students/{id}/report/`, `GET /students/{id}/tasks/`, `PATCH /students/{id}/tasks/{task_id}/`,
`POST /students/{id}/chat/`, `GET /students/{id}/quiz/topics/`, `POST /students/{id}/quiz/`,
`GET /students/{id}/quiz/{session_id}/`, `POST /students/{id}/quiz/{session_id}/submit/`,
`POST /students/{id}/quiz/{session_id}/questions/{question_id}/flag/`, and `GET /students/{id}/quiz/mastery/`.
Quiz lengths can be set from 1 to 20 questions. Questions require an available LLM; no fallback questions are
fabricated. In-progress responses never include answers or explanations. Errors are `{"detail": {"message": ..., "issues": [...]}}`.

## Troubleshooting
- *"Cannot reach the backend"*: start uvicorn first, from the project root; check `API_BASE_URL` in `.env`.
- `.env` is read when the backend starts; restart uvicorn after changing it. In PowerShell, an explicit
  `$env:LLM_MODEL` (or other environment variable) overrides the value in `.env`.
- A `503 Provider returned error` from a `:free` OpenRouter model is an upstream provider outage. The backend logs
  the failure and returns the deterministic report/chat fallback instead of crashing.
- Quiz generation returns an actionable rate-limit message when OpenRouter's free-model daily quota is exhausted.
  Wait for the reset or set `LLM_MODEL` to an available model with account credits.
- *Reports say "No AI model is configured"*: set `OPENROUTER_API_KEY`. The app calls OpenRouter directly; it does not use the OpenAI SDK. If the key is set but answers still say the AI was unavailable, check the backend log: the usual causes are an invalid key, no credit, a provider outage, or a model without tool-calling support (pick another `LLM_MODEL`). *"TAVILY_API_KEY is not configured"*: set it to get resources.
- *Image upload says OCR unavailable*: install Tesseract and make sure `tesseract --version` works in the same terminal.
- *PDF reads nothing*: marksheet layouts vary; use the manual table or a CSV/Excel file. Scanned PDFs need OCR.
- *Board grades look off*: bands are indicative for several boards; verify against your board's notification (see `app/data_engine/board_config.py`) and enter printed grades.
- Delete `student_feedback.db` to reset all data.

## Limits to know about
Marks alone cannot show which *topics* a student finds hard. Topic-level searches use quiz-derived weak topics when
available, then student-entered difficult topics. Topics proposed by the LLM are labelled as AI-suggested.
Resources are web search results, not vetted content; each card says so.
