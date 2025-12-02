# Rodin Frame Engine Prototype

This directory contains the source code for a functional prototype of the Rodin Frame Engine, a system designed to orchestrate and govern the behavior of Large Language Models (LLMs) in a structured, modular, and reusable way.

The prototype is implemented in Python using a production-ready asynchronous architecture. It uses LangGraph to manage the multi-step AI pipeline and Streamlit for a simple, interactive user interface.

## Prerequisites

- **Python 3.11+**
- **pyenv** (recommended for managing Python versions)
- **Poetry** (install via `pip install poetry` or [official installer](https://python-poetry.org/docs/#installation))
- **API Key** for Google Gemini, OpenAI, or Anthropic

## Quick Start

```bash
# 1. Set the correct Python version for this project
pyenv local 3.11.8

# 2. Install dependencies
poetry install

# 3. Create your API key file
echo 'GOOGLE_API_KEY="your-key-here"' > scripts/.env

# 4. Run the app
poetry run streamlit run scripts/frontend.py
```

That's it! The app opens in your browser at http://localhost:8501

## Project Philosophy: Composition Over Configuration

The core idea of the Frame Engine is to build complex, predictable, and safe AI systems by composing simple, single-responsibility components.

Instead of relying on a single, monolithic prompt, this architecture demonstrates how multiple Frames can be chained together in a pipeline. Some frames manage the core pedagogical logic, while others act as independent, reusable "guardrails" that enforce specific policies (like safety, age-appropriateness, or tone).

This prototype demonstrates this principle by composing four distinct frames to create the "Mnemonic Co-Creator Marty" experience.

## Code Layout

The project is structured as a self-contained Python application managed with Poetry.

```
code/
├── poetry.toml            # Poetry configuration (for local .venv)
├── pyproject.toml         # Poetry project file with dependencies
├── scripts/               # Executable scripts
│   ├── config.yaml        # Configuration for the application (LLM, logging)
│   ├── frontend.py        # The interactive web UI
│   └── .env               # API key storage (YOU CREATE THIS)
├── src/
│   └── backend/           # The installable Python package
│       ├── frame_engine/  # Core components of the Frame Engine
│       │   ├── __init__.py # Public exports
│       │   ├── core.py    # Abstract base classes and data structures
│       │   ├── engine.py  # The async, LangGraph-based pipeline orchestrator
│       │   └── llm.py     # Provider-agnostic LLM client factory
│       └── frames/        # Implementations of specific Frames
│           ├── __init__.py # Public exports
│           ├── marty.py   # The core pedagogical frame
│           ├── answer_checker.py # A reusable policy frame
│           ├── age_checker.py    # A reusable policy frame
│           └── policy_checker.py # A reusable meta-policy frame
├── tests/                 # Test suite (see tests/requirements.md)
│   ├── config.yaml        # Test configuration
│   ├── conftest.py        # Pytest fixtures
│   ├── requirements.md    # User stories for tests
│   └── .env               # Test API key (YOU CREATE THIS)
├── sessions/              # Output directory for saved session logs (auto-generated)
└── README.md              # This documentation file
```

## The Frame-Based Architecture in Action

This prototype runs a pipeline of four frames that work together to deliver the final user experience.

### 1. `MnemonicCoCreatorFrame` (The Conductor)

-   **Role**: This is the primary, stateful frame that manages the pedagogical flow of the session.
-   **Key Features**:
    -   **LLM-Powered Analysis**: In Slot 1, this frame makes its own internal LLM call to perform a deep analysis of the student's message, determining their intent, understanding level, and relevance to the task.
    -   **Stateful Session Management**: Uses `frame_memory` to track conversation phase, turn count, and participation.
    -   **Dynamic Prompt Shaping**: Uses `get_prompt_sections()` to contribute labeled sections to the prompt.
    -   **Turn-Taking Management**: Tracks recent speakers, detects monopolization, and suggests next speaker for fairness.
    -   **Speaking Time Tracking**: Estimates speaking duration based on message length.
    -   **Comprehension Monitoring**: Assesses understanding level per message via LLM analysis.
    -   **Focus Management**: Tracks off-topic duration and triggers redirection when needed.

### 2. `AnswerCheckerFrame` (The Knowledge Guardrail)

-   **Role**: A reusable, single-responsibility policy frame.
-   **Key Feature**: It validates the LLM's draft response to ensure it is **not** a direct answer or a close paraphrase from the provided learning material. This enforces the core principle that Marty facilitates, but does not give answers away.

### 3. `AgeCheckerFrame` (The Tone Guardrail)

-   **Role**: A reusable policy frame for ensuring appropriate language.
-   **Key Feature**: It uses an LLM to validate that the draft response is suitable for the average age of the students in the session (e.g., 14 years old), checking for simplicity and an encouraging tone.

### 4. `PolicyCheckerFrame` (The Meta Guardrail)

-   **Role**: A powerful, generic validation frame that ensures adherence to higher-level conversational policies.
-   **Key Feature**: It takes the analysis from the Marty frame and the draft response from the LLM, and makes its own validation call to check for three things:
    1.  **Persona**: Is the tone friendly and encouraging?
    2.  **Phase Goal**: Does the response align with the goal of the current phase (e.g., knowledge-building vs. mnemonic creation)?
    3.  **Complexity**: Is the response's complexity matched to the student's assessed level of understanding?

This layered, compositional approach ensures that the final output is not only pedagogically sound but also safe, appropriate, and consistent in its persona.

## Prompt Accumulation Pattern

The engine uses a **structured sections** approach for prompt shaping:

1.  **Phase 2a - Accumulation**: Each frame's `get_prompt_sections()` method returns labeled `PromptSection` objects.
2.  **Assembly**: The engine assembles all sections into a single prompt.
3.  **Phase 2b - Transformation**: Each frame's `shape_prompt()` method can optionally transform the final prompt (for advanced use cases).

### Debug Mode

For debugging, you can enable section labels in the prompt:

```python
engine = FrameEngine(
    frames=[...],
    llm_client=llm_client,
    include_section_labels=True  # Adds [Label] markers
)
```

With labels enabled, the prompt looks like:
```
[Marty - Persona & Knowledge]
You are 'Marty,' a friendly robot...

[Marty - Phase 2 Instructions]
Current Goal: Brainstorm Core Concepts...
```

Labels are **disabled by default** to keep prompts clean and save tokens.

## LLM Provider Configuration

The engine supports multiple LLM providers through a provider-agnostic factory in `llm.py`. Configure your provider in `config.yaml`:

```yaml
llm:
  # Supported providers: "google", "openai", "anthropic"
  provider: "google"
  
  # Model name (provider-specific)
  model_name: "gemini-2.5-flash-lite"
  
  # Optional temperature (0.0 to 1.0)
  # temperature: 0.7
```

### Supported Providers

| Provider | Model Examples | Environment Variable |
|----------|---------------|---------------------|
| Google | `gemini-2.5-flash-lite`, `gemini-2.5-flash`, `gemini-2.5-pro` | `GOOGLE_API_KEY` |
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo` | `OPENAI_API_KEY` |
| Anthropic | `claude-sonnet-4-20250514`, `claude-3-5-haiku-20241022` | `ANTHROPIC_API_KEY` |

### Installing Additional Providers

Google is included by default. For other providers:

```bash
# OpenAI only
poetry install --extras "openai"

# Anthropic only
poetry install --extras "anthropic"

# All providers
poetry install --extras "all-providers"
```

## How to Run the Prototype

Follow these steps from this directory (`.../frame_engine/code`).

### 1. Create the Environment File

The application requires an API key for your chosen provider. Create a file named `.env` inside the `scripts/` directory:

```bash
# scripts/.env
GOOGLE_API_KEY="your-actual-api-key-here"
```

Or for other providers:

```bash
# scripts/.env (for OpenAI)
OPENAI_API_KEY="your-actual-api-key-here"

# scripts/.env (for Anthropic)
ANTHROPIC_API_KEY="your-actual-api-key-here"
```

> **Note**: Never commit your `.env` file to version control.

### 2. Set up the Python Environment

This project uses `Poetry`. The `poetry.toml` file is already configured to create the virtual environment inside this project folder.

```bash
# From within the 'code' directory:
poetry install

# Or with additional providers:
poetry install --extras "all-providers"
```

### 3. Launch the Interactive App

Once the dependencies are installed, you can run the Streamlit application.

```bash
# From within the 'code' directory:
poetry run streamlit run scripts/frontend.py
```

This will start a local web server and open the interactive chat interface in your browser.

### 4. Run Tests

The test suite uses **actual LLM calls** (no mocking) to verify the system works end-to-end.

**Step 1**: Create the test environment file at `tests/.env`:

```bash
# tests/.env
GOOGLE_API_KEY="your-actual-api-key-here"
```

**Step 2**: Run the tests:

```bash
# Run all tests
poetry run python -m pytest

# Run with verbose output
poetry run python -m pytest -v

# Run a specific test file
poetry run python -m pytest tests/test_marty.py -v

# Run with debug output to see LLM calls
poetry run python -m pytest -v --log-cli-level=DEBUG
```

See `tests/requirements.md` for the user stories that drive the test suite.

## Public API

The package exports the following from `backend.frame_engine`:

```python
from backend.frame_engine import (
    # Core types
    Frame,              # Abstract base class for all frames
    FrameContext,       # TypedDict for turn state
    PromptSection,      # TypedDict for prompt contributions
    ValidationAction,   # Enum: PASS, FIX, REVISE, FAIL
    ValidationResult,   # TypedDict for validation output
    
    # Engine
    FrameEngine,        # The main orchestrator
    
    # LLM
    get_llm_client,     # Provider-agnostic factory
    LLMConfigError,     # Configuration error
    
    # Constants for inter-frame communication (avoid hardcoded frame names)
    CLEANED_MESSAGE_KEY,          # Key for cleaned user message
    SPEAKER_KEY,                  # Key for speaker name
    SESSION_PHASE_KEY,            # Key for session phase (1, 2, 3...)
    UNDERSTANDING_LEVEL_KEY,      # Key for understanding level assessment
    SUGGESTED_NEXT_SPEAKER_KEY,   # Key for suggested next speaker (turn-taking)
    CONSECUTIVE_SAME_SPEAKER_KEY, # Key for monopolization detection
)
```

And from `backend.frames`:

```python
from backend.frames import (
    AgeCheckerFrame,
    AnswerCheckerFrame,
    MnemonicCoCreatorFrame,
    PolicyCheckerFrame,
)
```
