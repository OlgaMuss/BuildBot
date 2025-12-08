"""The main Streamlit application for interacting with the Frame Engine.

This script provides a web-based user interface for configuring and running the
"Mnemonic Co-Creator Marty" frame. It allows users to define the learning
context, select a speaker, and engage in a real-time chat with the AI.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st
import yaml

# --- Constants (avoid magic strings) ---
_ROLE_USER = 'user'
_ROLE_ASSISTANT = 'assistant'
_DEFAULT_GREETING = "Hi! I'm Marty. Let's create a mnemonic together! What should we talk about first?"

# --- Environment Setup ---
# This setup is a bit more robust for Streamlit, which runs from a different context.
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
package_path = project_root / 'src'

if str(package_path) not in sys.path:
    sys.path.insert(0, str(package_path))

# Imports after sys.path modification (required for Streamlit context)
from backend.frame_engine.core import SessionLogger, TerminalLogger
from backend.frame_engine.engine import FrameEngine
from backend.frame_engine.llm import LLMConfigError, get_llm_client
from backend.frames.language_checker import LanguageCheckerFrame
from backend.frames.balanced_turns import BalancedTurnsFrame
from backend.frames.comprehension_tracker import ComprehensionTrackerFrame
from backend.frames.marty import MnemonicCoCreatorFrame
from backend.frames.phases_checker import PhasesCheckerFrame


# --- Helper Functions ---

def _clear_session_state() -> None:
    """Clears all session state to start fresh."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _load_and_display_env_status(config: dict[str, Any]) -> None:
    """Loads .env file and displays the LLM provider status in the sidebar."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        st.warning('`python-dotenv` not installed. Cannot load .env file.')
        return

    dotenv_path = script_dir / '.env'
    if dotenv_path.is_file():
        load_dotenv(dotenv_path=dotenv_path)
        st.info('Loaded API keys from .env file.')

    # Check for required API key
    llm_config = config.get('llm', {})
    provider = llm_config.get('provider', 'google').lower()
    env_var_map = {
        'google': 'GOOGLE_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
        'azure': 'AZURE_API_KEY',  # Add this line
    }
    required_key = env_var_map.get(provider)
    # Fallback for providers not in the map, though `llm.py` would catch this.
    if not required_key:
        st.error(f"Provider '{provider}' is not configured in the frontend's environment map.")
        return

    # Check for Azure-specific additional keys
    if provider == 'azure':
        if 'AZURE_ENDPOINT' not in os.environ:
            st.error('AZURE_ENDPOINT not found. Please add it to scripts/.env')
            return

    if required_key not in os.environ:
        st.error(f'{required_key} not found. Please add it to scripts/.env')
        return

    st.success(f'Using {provider.title()} ({llm_config.get("model_name", "default")})')


def _initialize_engine(
    topic: str,
    learning_material: str,
    mnemonic_type: str,
    participants: list[dict[str, Any]],
    target_age: int,
    config: dict[str, Any],
) -> tuple['FrameEngine', SessionLogger]:
    """Initializes the Frame Engine with all required frames and a session logger.

    Args:
        topic: The learning topic.
        learning_material: The source material for the mnemonic.
        mnemonic_type: The type of mnemonic (Story, Acronym, Song).
        participants: List of participant dictionaries with name and color.
        target_age: The target age for the session.
        config: The application configuration dictionary.

    Returns:
        A tuple of (FrameEngine instance, SessionLogger instance).

    Raises:
        LLMConfigError: If the LLM client cannot be initialized.
    """
    student_names = [p['name'] for p in participants]

    logging.info('Initializing session for students: %s (Target Age: %d)', student_names, target_age)

    # Get LLM client from config
    llm_config = config.get('llm', {})
    llm_client = get_llm_client(
        provider=llm_config.get('provider', 'google'),
        model_name=llm_config.get('model_name', 'gemini-2.5-flash-lite'),
        #temperature=llm_config.get('temperature'),
    )

    # Create the session logger (global for all frames)
    from datetime import datetime
    session_id = f"{topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session_logger = SessionLogger(session_id=session_id)
    session_logger.set_metadata('topic', topic)
    session_logger.set_metadata('mnemonic_type', mnemonic_type)
    session_logger.set_metadata('students', student_names)
    session_logger.set_metadata('target_age', target_age)
    session_logger.log('Session initialized')
    
    # Setup terminal logging to capture Python logging output
    sessions_dir = project_root / 'sessions'
    sessions_dir.mkdir(exist_ok=True)
    
    # Clean up any leftover terminal log files from previous sessions
    for old_log in sessions_dir.glob('*_terminal_log.md'):
        try:
            old_log.unlink()
        except Exception:
            pass
    
    terminal_log_path = sessions_dir / f"session_{session_id}_terminal_log.md"
    shared_log_file = open(terminal_log_path, 'w', encoding='utf-8')
    sys.stdout = TerminalLogger(str(terminal_log_path), stream=sys.stdout, shared_file=shared_log_file)
    sys.stderr = TerminalLogger(str(terminal_log_path), stream=sys.stderr, shared_file=shared_log_file)
    
    # Remove any old FileHandlers to prevent duplicate logging
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            root_logger.removeHandler(handler)
    
    # Capture Python logging module output to same file
    log_handler = logging.FileHandler(terminal_log_path, mode='a')
    log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(log_handler)
    
    session_logger._shared_log_file = shared_log_file
    session_logger._log_handler = log_handler

    # Compose the frame pipeline
    marty_frame = MnemonicCoCreatorFrame(
        topic=topic,
        learning_material=learning_material,
        students=student_names,
        mnemonic_type=mnemonic_type,
        llm_client=llm_client,
    )

    comprehension_frame = ComprehensionTrackerFrame(
        learning_material=learning_material,
        students=student_names,
        llm_client=llm_client,
    )

    balanced_turns_frame = BalancedTurnsFrame(students=student_names)
    language_checker_frame = LanguageCheckerFrame(
        target_age=target_age,
        llm_client=llm_client,
        learning_material=learning_material,
    )

    engine = FrameEngine(
        frames=[
            marty_frame,
            comprehension_frame,
            balanced_turns_frame,
            language_checker_frame,
            PhasesCheckerFrame(llm_client=llm_client),
        ],
        llm_client=llm_client,
        session_logger=session_logger,
    )

    return engine, session_logger


# --- Config and Logging ---
def load_config() -> dict[str, Any]:
    """Loads the main configuration from the `config.yaml` file."""
    config_path = script_dir / 'config.yaml'
    if not config_path.is_file():
        # Use st.error for user-facing errors in the UI
        st.error(f'Configuration file not found at {config_path}')
        return {}
    with config_path.open('r') as f:
        return yaml.safe_load(f)


config = load_config()
log_level = config.get('log_level', 'INFO').upper()
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,  # Direct logs to stdout for Streamlit compatibility
)


# --- Load external content ---
def load_learning_material() -> str:
    """Loads the learning material from the markdown file."""
    # The markdown file is located at the parent of the 'code' directory
    material_path = project_root.parent / 'microcontrollers.md'
    try:
        return material_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        st.error(f'Learning material file not found at {material_path}')
        return 'Error: Learning material not found.'


# --- Page Configuration ---
st.set_page_config(
    page_title='Marty Mnemonic Co-Creator',
    page_icon='🤖'
)

st.title('🤖 Marty Mnemonic Co-Creator')

# --- Session State Initialization ---
if 'participants' not in st.session_state:
    # Default participants for the first run
    st.session_state.participants = [
        {'name': 'Red', 'color': '#FF4B4B'},
        {'name': 'Green', 'color': '#2BCB54'},
        {'name': 'Blue', 'color': '#4B7EFF'},
    ]

# --- Sidebar for Configuration ---
with st.sidebar:
    st.header('Configuration')

    # Load .env variables and display provider status
    _load_and_display_env_status(config)

    with st.expander('Learning Experience', expanded=True):
        topic = st.text_input('Topic', 'Microcontrollers')
        target_age = st.number_input('Target Age for Session', min_value=5, max_value=99, value=14)
        learning_material = st.text_area(
            'Learning Material',
            value=load_learning_material(),
            height=300,
        )
        mnemonic_type = st.selectbox('Mnemonic Type', ['Poem', 'Story', 'Jokes'])

    st.subheader('Participants')

    # Display current participants and remove button
    for i, p in enumerate(st.session_state.participants):
        cols = st.columns([0.8, 0.2])
        cols[0].write(f"**{p['name']}**")
        if cols[1].button('X', key=f'remove_{i}'):
            st.session_state.participants.pop(i)
            st.rerun()

    # Form to add a new participant
    with st.form('new_participant_form'):
        st.write('Add New Participant:')
        cols = st.columns([0.7, 0.3])
        new_name = cols[0].text_input('Name', label_visibility='collapsed')
        new_color = cols[1].color_picker('Color', label_visibility='collapsed')

        if st.form_submit_button('Add'):
            if new_name:
                st.session_state.participants.append(
                    {'name': new_name, 'color': new_color}
                )
                st.rerun()

    st.subheader('Session Control')
    if st.button('Start New Session'):
        _clear_session_state()
        st.rerun()

    if st.button('End & Save Session'):
        if 'engine' not in st.session_state or 'frame_memory' not in st.session_state:
            st.warning('No active session to save.')
        else:
            # Save session (automatically cleans up terminal logging)
            final_state_for_saving = {
                'frame_memory': st.session_state.get('frame_memory', {}),
            }
            asyncio.run(st.session_state.engine.end_session(final_state_for_saving))

            st.success('Session saved successfully.')
            _clear_session_state()
            st.rerun()

# --- Main Chat Interface ---

# Initialize engine on first run
if 'engine' not in st.session_state:
    if not st.session_state.participants:
        st.error('Please add at least one participant to start a session.')
        st.stop()

    try:
        engine, session_logger = _initialize_engine(
            topic=topic,
            learning_material=learning_material,
            mnemonic_type=mnemonic_type,
            participants=st.session_state.participants,
            target_age=target_age,
            config=config,
        )
        st.session_state.engine = engine
        st.session_state.session_logger = session_logger
        st.session_state.frame_memory = {}
        st.session_state.conversation_history = []
        st.session_state.messages = [{'role': _ROLE_ASSISTANT, 'content': _DEFAULT_GREETING}]
        logging.info('Session initialized successfully.')
    except (LLMConfigError, ValueError, FileNotFoundError) as e:
        logging.error('Initialization failed: %s', e, exc_info=True)
        st.error(f'Initialization failed: {e}')
        st.stop()


# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message['role']):
        st.markdown(message['content'])


def _get_student_names() -> list[str]:
    """Returns the list of student names from participants."""
    if not st.session_state.participants:
        return ['User']
    return [p['name'] for p in st.session_state.participants]


# --- User Input Section ---
student_names = _get_student_names()

# Create a container for the input controls at the bottom
input_container = st.container()
with input_container:
    col1, col2 = st.columns([1, 4])
    with col1:
        speaker = st.selectbox('Speaker', options=student_names, label_visibility='collapsed')
    with col2:
        user_input_text = st.chat_input('What would you like to say to Marty?', key='user_input')

# Accept user input
if user_input_text and speaker:
    formatted_input = f'{speaker}: {user_input_text}'

    # Add user message to chat history
    st.session_state.messages.append({'role': _ROLE_USER, 'content': formatted_input})
    with st.chat_message(_ROLE_USER):
        st.markdown(formatted_input)

    # Get response from the Frame Engine
    with st.chat_message(_ROLE_ASSISTANT):
        with st.spinner('Marty is thinking...'):
            result = asyncio.run(st.session_state.engine.ainvoke(
                user_input=formatted_input,
                conversation_history=st.session_state.get('conversation_history', []),
                frame_memory=st.session_state.get('frame_memory', {}),
            ))

            response = result['response']

            # Update state for the next turn
            st.session_state.frame_memory = result['final_state']['frame_memory']
            st.session_state.conversation_history = result['final_state']['conversation_history']

            st.markdown(response)

    # Add assistant response to chat history
    st.session_state.messages.append({'role': _ROLE_ASSISTANT, 'content': response})

    # Rerun to display new messages and clear input (standard Streamlit pattern)
    st.rerun()
