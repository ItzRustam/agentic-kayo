# Agentic Kayo

**Agentic Kayo** is a voice-enabled AI assistant with a Streamlit interface, bounded tool orchestration (built around LangChain Core without LangGraph), offline speech recognition, online text-to-speech, and isolated Python execution.

---

## Architecture Overview

```text
                         ┌──────────────────────────┐
                         │       Streamlit UI       │
                         │ Chat · Dashboard · Voice │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │    Application Layer     │
                         │ input routing / session  │
                         └───────┬──────────┬───────┘
                                 │          │
                    ┌────────────▼───┐  ┌───▼────────────────┐
                    │ Voice Pipeline │  │ Context & Profile  │
                    │ Vosk → text    │  │ user_info.json     │
                    │ gTTS ← text    │  │ Streamlit session  │
                    └────────────┬───┘  └───┬────────────────┘
                                 │          │
                         ┌───────▼──────────▼───────┐
                         │    Agent Orchestrator    │
                         │ manual tool-call loop    │
                         └───────────┬──────────────┘
                                     │
                   ┌─────────────────┴─────────────────┐
                   │                                   │
          ┌────────▼─────────┐               ┌─────────▼────────┐
          │ Primary LLM      │               │ Codegen LLM      │
          │ Gemini via       │               │ OpenRouter via   │
          │ LangChain        │               │ LangChain        │
          └────────┬─────────┘               └──────────────────┘
                   │
          ┌────────▼─────────┐
          │ Tool Registry    │
          │ web_search       │
          │ search_wikipedia │
          │ file tools       │
          │ Python runner    │
          │ send_mail        │
          │ open_website     │
          │ utilities        │
          └──────────────────┘
```

---

## Key Features

1. **Dual LLM Architecture**:
   - **Primary Model**: Google Gemini (via `langchain-google-genai`) for reasoning, general conversation, and tool orchestration.
   - **Codegen Model**: OpenRouter (via `langchain-openrouter`) for dedicated high-quality code generation.

2. **Voice Pipeline**:
   - **STT (Speech-to-Text)**: Local, offline transcription via **Vosk** using the US English small model (`models/en-small`).
   - **Browser Microphone Control**: Directly records in the user's browser via Streamlit's audio input.
   - **TTS (Text-to-Speech)**: Online text-to-speech via **gTTS** (MP3 audio). Configurable in the sidebar for automatic speech or per-message playback controls.

3. **Safe Bounded Tool Registry**:
   - `web_search`: Structured web search with URL, title, and concise snippets.
   - `search_wikipedia`: Concise summary only with canonical article URL.
   - `open_website`: Client-side clickable links for validated HTTP/HTTPS URLs.
   - `create_file`, `read_file`, `edit_file`, `list_files`, `search_files`: Safe workspace file operations.
   - `delete_file`: Confirmation-gated workspace file deletion.
   - `run_python_code`, `run_python_file`: Confirmation-gated Python 3.13 code execution in an isolated runner container.
   - `calculate`: Restricted AST arithmetic evaluator (no `eval()` or `exec()`).
   - `get_current_datetime`: Timezone-aware local time and ISO timestamps.
   - `send_mail`: Confirmation-gated SMTP email sending with preview and sidebar sender identity.

4. **Safety & Security**:
   - Explicit UI confirmation gates for sensitive actions (`send_mail`, `delete_file`, `run_python_code`, `run_python_file`).
   - Workspace boundary enforcement: path traversal (`..`), symlink escapes, and access to secrets (`.env`, `.git`) are strictly forbidden.
   - Secrets separation: `.env` is loaded only in the main application; the Python runner receives zero credentials and runs as non-root.

---

## Directory Structure

```text
agentic-kayo/
├── app.py                   # Main Streamlit application entrypoint
├── Dockerfile               # Debian-based container definition
├── docker-compose.yml       # Multi-service topology (Kayo app + isolated runner)
├── setup.sh                 # Environment setup script (uv, Python 3.13)
├── requirements.txt         # Project dependencies
├── user_info.json           # User profile storage (name, email, preferences)
├── .env.example             # Environment configuration template
├── models/
│   └── en-small/            # Vosk offline US English small model
├── src/
│   ├── config.py            # Central configuration loader
│   ├── storage/
│   │   └── user_info.py     # Profile JSON reader and updater
│   ├── llm/
│   │   ├── factory.py       # Gemini and OpenRouter model initialization
│   │   └── codegen.py       # Dedicated code generation service
│   ├── tools/
│   │   ├── registry.py      # Unified tool registry & LangChain binding
│   │   ├── web_search.py    # Structured web search
│   │   ├── search_wikipedia.py # Wikipedia summary search
│   │   ├── open_website.py  # Link validation
│   │   ├── files.py         # Safe workspace file operations
│   │   ├── python_execution.py # Python execution client
│   │   ├── utilities.py     # AST calculation & datetime
│   │   └── send_mail.py     # SMTP email sender
│   ├── runner/
│   │   └── server.py        # Isolated Python runner service
│   ├── agent/
│   │   ├── orchestrator.py  # Bounded manual tool-calling loop
│   │   ├── context.py       # Conversation history builder
│   │   └── prompts.py       # System prompt assembly
│   ├── voice/
│   │   ├── stt.py           # Vosk transcription
│   │   ├── tts.py           # gTTS audio generation
│   │   └── microphone.py    # Audio input processing
│   └── ui/
│       └── dashboard.py     # Streamlit UI tabs & components
└── tests/
    ├── test_config.py
    ├── test_profile.py
    ├── test_llm.py
    ├── test_tools.py
    ├── test_agent.py
    └── test_voice.py
```

---

## Setup & Running

### 1. Configuration

Copy the example environment file:
```bash
cp .env.example .env
```
Fill in your API keys in `.env`:
```dotenv
GOOGLE_API_KEY=your_gemini_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 2. Running Locally

Install dependencies using `setup.sh`:
```bash
chmod +x setup.sh && ./setup.sh
```

Run Streamlit:
```bash
source .venv/bin/activate
streamlit run app.py
```

### 3. Running with Docker Compose

Build and launch both the Streamlit app and the isolated runner:
```bash
docker compose build
docker compose up
```

Open `http://localhost:8501` in your browser.

---

## Running Automated Tests

Run the full test suite:
```bash
./.venv/bin/python -m unittest discover tests
```
