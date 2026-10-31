"""Product documentation for the Student Feedback Agent."""
from __future__ import annotations

import streamlit as st

import ui


ui.setup("Documentation", "D")

st.markdown(
    """
    <style>
    .doc-hero {
        padding: 2rem 2.2rem;
        border-radius: 16px;
        background: linear-gradient(135deg, #1F2A44 0%, #0E7C86 100%);
        color: white;
        margin-bottom: 1.5rem;
    }
    .doc-hero h1, .doc-hero p { color: white; }
    .doc-hero h1 { margin-bottom: .35rem; font-size: 2.35rem; }
    .doc-hero p { margin: 0; opacity: .9; font-size: 1.05rem; }
    .doc-card {
        border: 1px solid #E1E6EC;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        min-height: 120px;
        background: #FFFFFF;
        margin-bottom: .75rem;
    }
    .doc-card h4 { color: #1F2A44; margin: 0 0 .45rem; }
    .doc-card p { color: #5B667A; margin: 0; line-height: 1.5; }
    .doc-label {
        color: #0E7C86;
        text-transform: uppercase;
        letter-spacing: .08em;
        font-size: .75rem;
        font-weight: 600;
    }
    .doc-note {
        border-left: 4px solid #D98E04;
        background: #FFF8E8;
        border-radius: 4px;
        padding: .8rem 1rem;
        color: #5B667A;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="doc-hero">
        <div class="doc-label" style="color:#BFE8EA;">Product guide</div>
        <h1>Student Feedback Agent</h1>
        <p>A practical academic companion for turning examination results into clear insights,
        focused practice, and an actionable improvement plan.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "Use this page as the complete guide to the product. Start with the Quick start section, "
    "then follow the workflow from student information to analysis and practice."
)

st.header("Contents")
contents = [
    ("01", "What the tool does", "Purpose, users, and the value of the platform"),
    ("02", "Quick start", "The recommended workflow from setup to action"),
    ("03", "Product components", "What each area of the application provides"),
    ("04", "Features in detail", "Analysis, reports, resources, chat, and quizzes"),
    ("05", "How the analysis works", "Data flow, calculations, and AI boundaries"),
    ("06", "Technology and architecture", "The stack and how the services fit together"),
    ("07", "Configuration and operations", "Environment variables, deployment, and security"),
    ("08", "Troubleshooting and best practices", "Common issues and reliable usage patterns"),
]
for number, title, summary in contents:
    st.markdown(
        f'<div class="doc-card"><span class="doc-label">{number}</span>'
        f"<h4>{title}</h4><p>{summary}</p></div>",
        unsafe_allow_html=True,
    )

st.header("1. What the tool does")
st.markdown(
    """
    Student Feedback Agent helps students, teachers, and academic advisors move from raw
    examination marks to an understandable improvement plan. It combines deterministic
    calculations with optional AI assistance, so the important numerical results remain
    reproducible while written guidance can be personalized.

    ### Who it is for

    - **Students:** understand strengths, weaknesses, progress, and what to practise next.
    - **Parents and mentors:** see evidence-based progress without manually calculating every result.
    - **Teachers and advisors:** review structured performance information and generate focused guidance.
    - **Academic programs:** organize student results, reports, tasks, and quiz evidence in one workflow.

    ### The central promise

    The application does not ask an AI model to calculate marks. Pandas and NumPy perform the
    numerical analysis first. AI is used only where it adds value, such as narrative explanations,
    study suggestions, resource discovery, and conversational support.
    """
)

st.header("2. Quick start")
st.subheader("Recommended user workflow")
steps = [
    ("1", "Create a student profile", "Enter the learner's board, grade, academic year, goals, difficult subjects, and target percentage."),
    ("2", "Add examination results", "Enter rows manually or upload a CSV, Excel file, PDF, or image marksheet."),
    ("3", "Review and save marks", "Check extracted rows, correct any issues, and save only validated results."),
    ("4", "Open the dashboard", "Review overview metrics, subject performance, comparisons, charts, and weaknesses."),
    ("5", "Generate the report", "Ask the agent to create recommendations and, when configured, search learning resources."),
    ("6", "Turn advice into action", "Track roadmap tasks, ask the academic chat questions, and practise weak topics with quizzes."),
]
for number, title, description in steps:
    with st.container(border=True):
        left, right = st.columns([1, 8])
        left.metric("Step", number)
        right.markdown(f"**{title}**  \n{description}")

with st.expander("What data should I prepare?"):
    st.markdown(
        """
        The most useful input is one row per subject per examination with:

        - `subject`
        - `obtained`
        - `total`
        - optional `exam`, `exam_type`, and `grade`

        For Excel workbooks with multiple sheets, sheet names can be used as examination names
        when an `exam` column is not present. Always review extracted rows before saving.
        """
    )

st.header("3. Product components")
component_columns = st.columns(2)
components = [
    ("Student Information", "Creates and selects student profiles, including board, grade, goals, target percentage, difficult subjects, difficult topics, preferred resource types, and language."),
    ("Upload Marksheet", "Accepts manual entry and supported file uploads. It previews extracted data, reports validation problems, and prevents unverified rows from being silently stored."),
    ("Academic Dashboard", "Presents overall metrics, subject results, examination comparisons, distributions, visual analytics, weaknesses, resources, and generated reports."),
    ("Improvement Roadmap", "Converts recommendations into trackable tasks so a student can work through a prioritized plan."),
    ("AI Academic Chat", "Answers questions using the selected student's stored results and analysis context. It uses a configured model when available and a rules-based fallback otherwise."),
    ("Practice Quiz", "Generates topic-focused questions for weak subjects, supports MCQ and Q/A formats, hides answers during an active quiz, and records mastery evidence."),
    ("Data Analysis Lab", "Provides deeper summaries such as distributions, z-scores, correlations, trends, marks-lost analysis, target planning, weighted scores, pivots, and exports."),
    ("Documentation", "Explains the complete product, workflow, technical design, configuration, and operational guidance."),
]
for index, (title, description) in enumerate(components):
    with component_columns[index % 2]:
        st.markdown(
            f'<div class="doc-card"><h4>{title}</h4><p>{description}</p></div>',
            unsafe_allow_html=True,
        )

st.header("4. Features in detail")
feature_tabs = st.tabs(
    ["Data and validation", "Performance intelligence", "AI and resources", "Practice and planning"]
)

with feature_tabs[0]:
    st.subheader("Flexible marksheet input")
    st.markdown(
        """
        Results can be entered directly or extracted from CSV, Excel, PDF, PNG, and JPG files.
        The extraction process is intentionally review-first: extracted rows are displayed before
        they can be saved.

        ### Validation protections

        - Missing, non-numeric, or invalid marks are reported.
        - Obtained marks cannot exceed the total.
        - Duplicate and summary rows are handled during cleaning.
        - Subject names are normalized through aliases.
        - Invalid submissions return structured field and row-level issues.
        - Scanned documents require the optional Tesseract binary for OCR.
        """
    )
    st.markdown('<div class="doc-note">Tip: CSV or Excel is usually the most reliable format for a large marksheet.</div>', unsafe_allow_html=True)

with feature_tabs[1]:
    st.subheader("Evidence-based performance feedback")
    st.markdown(
        """
        The analysis engine calculates results independently from the language model. It can
        report overall percentage, average subject score, grades, highest and lowest subjects,
        distributions, standard deviation, comparisons, trends, consistency, outliers, and
        marks-lost priorities.

        ### Weakness and strength signals

        A subject can be flagged using several kinds of evidence:

        - absolute performance against a threshold or board pass mark;
        - performance relative to the student's own average;
        - decline compared with an earlier examination;
        - inconsistency across examinations;
        - shortfall against a personal target;
        - a subject the student explicitly reported as difficult.

        Each result includes explanations so a recommendation is connected to observable data.
        """
    )

with feature_tabs[2]:
    st.subheader("Optional AI assistance")
    st.markdown(
        """
        When `OPENROUTER_API_KEY` is configured in the backend deployment, the application can
        use the selected OpenRouter model for:

        - report narrative generation;
        - personalized study advice;
        - academic chat;
        - practice quiz question generation;
        - resource-search planning.

        Tavily can optionally provide web search results for learning resources. AI-generated
        text is labeled in the interface, and deterministic fallback behavior keeps the core
        product usable when a provider is unavailable.
        """
    )
    st.markdown('<div class="doc-note">AI suggestions are guidance, not an official grade, diagnosis, or substitute for a teacher.</div>', unsafe_allow_html=True)

with feature_tabs[3]:
    st.subheader("From insight to improvement")
    st.markdown(
        """
        The roadmap turns report recommendations into tasks. The quiz feature then provides a
        focused practice loop:

        1. Select a subject with a measurable weakness.
        2. Choose a suggested topic or describe a specific topic.
        3. Generate a short MCQ or Q/A practice session.
        4. Submit answers and review the result after completion.
        5. Repeat across sessions to build topic-level mastery evidence.

        Mastery is deliberately conservative: the default verdict requires at least eight
        answered questions across two completed quiz sessions.
        """
    )

st.header("5. How the analysis works")
st.subheader("End-to-end data flow")
st.code(
    """Student profile + marksheet
            |
            v
   Cleaning and validation
            |
            v
   Pandas / NumPy analysis
            |
     +------+------+
     |             |
     v             v
  Dashboard     Agent context
                   |
       +-----------+-----------+
       |           |           |
       v           v           v
    Report       Chat        Quiz
       |
       v
 Optional Tavily learning resources""",
    language="text",
)
st.markdown(
    """
    ### Separation of responsibilities

    - **Data engine:** owns calculations, cleaning, comparisons, and statistical summaries.
    - **API layer:** validates requests, isolates students, and exposes backend operations.
    - **Streamlit frontend:** presents workflows, charts, forms, and user feedback.
    - **Agent layer:** interprets verified analysis results and produces written guidance.
    - **Database layer:** stores student profiles, results, reports, tasks, chats, and quiz sessions.

    This separation prevents a generated response from becoming the source of truth for numerical
    performance data.
    """
)

st.header("6. Technology and architecture")
stack = [
    ("Frontend", "Streamlit", "Interactive multipage interface, forms, metrics, tables, charts, and downloads."),
    ("Backend", "FastAPI", "Typed HTTP API, request validation, lifecycle startup, error handling, and OpenAPI docs."),
    ("Server", "Uvicorn", "ASGI server used to run the FastAPI application."),
    ("Data analysis", "Pandas and NumPy", "Cleaning, aggregation, statistical analysis, comparisons, and planning calculations."),
    ("Database", "SQLAlchemy + SQLite", "ORM models and local development persistence; use a production database for cloud scale."),
    ("Validation", "Pydantic + pydantic-settings", "Typed schemas and environment-based configuration."),
    ("AI integration", "LangChain Core + OpenRouter", "Structured agent steps, tool context, and optional language-model assistance."),
    ("Resource search", "Tavily", "Optional web search for relevant learning resources."),
    ("Visualization", "Matplotlib, Seaborn, Plotly", "Static charts and interactive performance visualizations."),
    ("Documents", "PyMuPDF, openpyxl, python-docx, pytesseract", "Reading common marksheet and document formats, with optional OCR."),
]
st.table({"Layer": [row[0] for row in stack], "Technology": [row[1] for row in stack], "Role": [row[2] for row in stack]})

st.subheader("Backend entry point")
st.code("app.main:app", language="text")
st.caption("The FastAPI application is exposed as a module-level app object and can be run with the FastAPI CLI or Uvicorn.")

st.header("7. Configuration and operations")
st.subheader("Local development")
st.code(
    """uv venv .venv
uv pip install -r requirements.txt --python .venv\\Scripts\\python.exe
.\\.venv\\Scripts\\Activate.ps1
Copy-Item .env.example .env
python -m fastapi run""",
    language="powershell",
)

st.subheader("Cloud deployment")
st.markdown(
    """
    The backend and frontend are separate deployments:

    1. Deploy the FastAPI backend with the official `fastapi deploy` command.
    2. Add backend secrets and configuration to the FastAPI Cloud environment.
    3. Set `API_BASE_URL` in Streamlit Cloud Secrets to the public backend URL.
    4. Add the Streamlit app's allowed origin to backend `CORS_ORIGINS` when required.
    5. Redeploy or reboot both applications after changing environment variables.
    """
)
st.code(
    """# Streamlit Cloud Secrets (TOML)
API_BASE_URL = "https://your-backend.fastapicloud.dev"

# Backend environment variables
OPENROUTER_API_KEY = "replace-with-a-new-key"
TAVILY_API_KEY = "replace-with-a-new-key"
DATABASE_URL = "your-production-database-url"
CORS_ORIGINS = "https://your-app.streamlit.app"
""",
    language="toml",
)

st.subheader("Configuration reference")
st.table(
    {
        "Variable": [
            "API_BASE_URL",
            "OPENROUTER_API_KEY",
            "LLM_MODEL",
            "OPENROUTER_BASE_URL",
            "TAVILY_API_KEY",
            "DATABASE_URL",
            "CORS_ORIGINS",
            "UPLOAD_DIRECTORY / REPORT_DIRECTORY / CHART_DIRECTORY",
        ],
        "Used by": [
            "Streamlit frontend",
            "FastAPI backend",
            "FastAPI backend",
            "FastAPI backend",
            "FastAPI backend",
            "FastAPI backend",
            "FastAPI backend",
            "FastAPI backend",
        ],
        "Purpose": [
            "Public backend address",
            "Optional language-model access",
            "OpenRouter model name",
            "OpenRouter API endpoint",
            "Optional resource search",
            "SQLAlchemy database connection",
            "Allowed browser origins",
            "Runtime storage locations",
        ],
    }
)

st.header("8. Troubleshooting and best practices")
with st.expander("The frontend says it cannot reach the backend"):
    st.markdown(
        """
        Confirm that Streamlit Cloud Secrets contains the public backend URL:
        `API_BASE_URL = "https://your-backend.fastapicloud.dev"`.
        Do not use `127.0.0.1` or `localhost` for a cloud frontend. Check that the backend
        `/health/` endpoint is reachable and reboot the Streamlit app after changing secrets.
        """
    )

with st.expander("The app says no AI model is configured"):
    st.markdown(
        """
        The key must be configured in the **backend** deployment, not only in Streamlit Cloud.
        Open the backend `/health/` endpoint and confirm `llm_configured` is `true`. If it is
        false, add `OPENROUTER_API_KEY` to the backend environment and redeploy.
        """
    )

with st.expander("A Streamlit page reports ModuleNotFoundError"):
    st.markdown(
        """
        Ensure the latest repository revision is deployed and the app has been rebooted.
        Streamlit pages run with the `frontend` directory on the import path, so frontend
        components use imports that support both `components` and `frontend.components`.
        """
    )

with st.expander("OCR or a document upload does not work"):
    st.markdown(
        """
        CSV and Excel are the most predictable formats. Text PDFs can work with PyMuPDF.
        Scanned PDFs and images require the Tesseract system binary in addition to the
        Python `pytesseract` package.
        """
    )

with st.expander("Security checklist"):
    st.markdown(
        """
        - Never commit `.env`, API keys, passwords, or production database URLs.
        - Store secrets in FastAPI Cloud and Streamlit Cloud secret managers.
        - Rotate any key that has been pasted into a chat, screenshot, issue, or log.
        - Use a managed production database instead of local SQLite for cloud persistence.
        - Restrict `CORS_ORIGINS` to the actual frontend URL in production.
        - Keep uploaded documents and generated reports in storage appropriate for the deployment environment.
        """
    )

st.header("Quick reference")
quick_left, quick_right = st.columns(2)
with quick_left:
    st.markdown(
        """
        **Start a new analysis**

        1. Student Information
        2. Upload Marksheet
        3. Academic Dashboard
        4. Generate AI report
        """
    )
with quick_right:
    st.markdown(
        """
        **Continue improving**

        1. Review weaknesses
        2. Open the Improvement Roadmap
        3. Ask the AI Academic Chat
        4. Practise with Practice Quiz
        """
    )

st.divider()
st.caption(
    "Student Feedback Agent combines calculated academic evidence with optional AI guidance. "
    "Always verify official grades and important academic decisions with the relevant school or board."
)
