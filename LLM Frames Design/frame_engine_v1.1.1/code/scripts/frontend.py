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
from backend.frame_engine.core import SessionLogger, SessionVerbosity  # noqa: E402
from backend.frame_engine.engine import FrameEngine  # noqa: E402
from backend.frame_engine.llm import LLMConfigError, get_llm_client  # noqa: E402
from backend.frames.age_checker import AgeCheckerFrame  # noqa: E402
from backend.frames.answer_checker import AnswerCheckerFrame  # noqa: E402
from backend.frames.comprehension_tracker import ComprehensionTrackerFrame  # noqa: E402
from backend.frames.marty import MnemonicCoCreatorFrame  # noqa: E402
from backend.frames.policy_checker import PolicyCheckerFrame  # noqa: E402


# --- Helper Functions ---

def _clear_session_state() -> None:
    """Clears all session state to start fresh."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _calculate_average_age(participants: list[dict[str, Any]]) -> int:
    """Calculates the average age of participants."""
    if not participants:
        return 14  # Default age
    return int(sum(p['age'] for p in participants) / len(participants))


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
    }
    required_key = env_var_map.get(provider, 'GOOGLE_API_KEY')

    if required_key not in os.environ:
        st.error(f'{required_key} not found. Please add it to scripts/.env')
        return

    st.success(f'Using {provider.title()} ({llm_config.get("model_name", "default")})')


def _initialize_engine(
    topic: str,
    learning_material: str,
    mnemonic_type: str,
    participants: list[dict[str, Any]],
    config: dict[str, Any],
    verbosity: SessionVerbosity = SessionVerbosity.NORMAL,
) -> tuple['FrameEngine', SessionLogger]:
    """Initializes the Frame Engine with all required frames and a session logger.

    Args:
        topic: The learning topic.
        learning_material: The source material for the mnemonic.
        mnemonic_type: The type of mnemonic (Story, Acronym, Song).
        participants: List of participant dictionaries with name, color, age.
        config: The application configuration dictionary.
        verbosity: The verbosity level for session logging.

    Returns:
        A tuple of (FrameEngine instance, SessionLogger instance).

    Raises:
        LLMConfigError: If the LLM client cannot be initialized.
    """
    student_names = [p['name'] for p in participants]
    average_age = _calculate_average_age(participants)

    logging.info('Initializing session for students: %s (Avg. Age: %d)', student_names, average_age)

    # Get LLM client from config
    llm_config = config.get('llm', {})
    llm_client = get_llm_client(
        provider=llm_config.get('provider', 'google'),
        model_name=llm_config.get('model_name', 'gemini-2.5-flash-lite'),
        temperature=llm_config.get('temperature'),
    )

    # Create the session logger (global for all frames)
    from datetime import datetime
    session_id = f"{topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session_logger = SessionLogger(session_id=session_id, verbosity=verbosity)
    session_logger.set_metadata('topic', topic)
    session_logger.set_metadata('mnemonic_type', mnemonic_type)
    session_logger.set_metadata('students', student_names)
    session_logger.log('Session initialized')

    # Compose the frame pipeline
    marty_frame = MnemonicCoCreatorFrame(
        topic=topic,
        learning_material=learning_material,
        students=student_names,
        mnemonic_type=mnemonic_type,
        phase_config=config.get('phases', {}),
        llm_client=llm_client,
    )

    comprehension_frame = ComprehensionTrackerFrame(
        learning_material=learning_material,
        students=student_names,
        llm_client=llm_client,
    )

    engine = FrameEngine(
        frames=[
            marty_frame,
            comprehension_frame,
            AnswerCheckerFrame(learning_material=learning_material, llm_client=llm_client),
            AgeCheckerFrame(target_age=average_age, llm_client=llm_client),
            PolicyCheckerFrame(llm_client=llm_client),
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
        {'name': 'Red', 'color': '#FF4B4B', 'age': 14},
        {'name': 'Green', 'color': '#2BCB54', 'age': 15},
        {'name': 'Blue', 'color': '#4B7EFF', 'age': 14},
    ]

# --- Sidebar for Configuration ---
with st.sidebar:
    st.header('Configuration')

    # Load .env variables and display provider status
    _load_and_display_env_status(config)

    with st.expander('Learning Experience', expanded=False):
        topic = st.text_input('Topic', 'Microcontrollers')
        learning_material = st.text_area(
            'Learning Material',
            'A microcontroller is a compact integrated circuit designed to govern '
            'a specific operation in an embedded system.\n'
            'Key components include:\n'
            "1.  CPU (Central Processing Unit): The 'brain' that executes instructions.\n"
            '2.  Memory: Flash (Program Memory) and RAM (Data Memory).\n'
            '3.  Peripherals (I/O): GPIO, ADC, Communication Interfaces, Timers.\n'
            'An example is the ESP32, which also includes built-in Wi-Fi and Bluetooth.',
            height=250,
        )
        mnemonic_type = st.selectbox('Mnemonic Type', ['Story', 'Acronym', 'Song'])

    with st.expander('Session Logging', expanded=False):
        verbosity_options = {
            'Minimal': SessionVerbosity.MINIMAL,
            'Normal': SessionVerbosity.NORMAL,
            'Verbose (debug)': SessionVerbosity.VERBOSE,
        }
        verbosity_label = st.selectbox(
            'Log Verbosity',
            options=list(verbosity_options.keys()),
            index=1,  # Default to Normal
            help='MINIMAL: summary only | NORMAL: turn logs | VERBOSE: full slot details',
        )
        selected_verbosity = verbosity_options[verbosity_label]

    st.subheader('Participants')

    # Display current participants and remove button
    for i, p in enumerate(st.session_state.participants):
        cols = st.columns([0.5, 0.3, 0.2])
        cols[0].write(f"**{p['name']}**")
        cols[1].write(f"Age: {p['age']}")
        if cols[2].button('X', key=f'remove_{i}'):
            st.session_state.participants.pop(i)
            st.rerun()

    # Form to add a new participant
    with st.form('new_participant_form'):
        st.write('Add New Participant:')
        cols = st.columns([0.5, 0.3, 0.2])
        new_name = cols[0].text_input('Name', label_visibility='collapsed')
        new_color = cols[1].color_picker('Color', label_visibility='collapsed')
        new_age = cols[2].number_input('Age', min_value=5, max_value=99, value=14, label_visibility='collapsed')

        if st.form_submit_button('Add'):
            if new_name:
                st.session_state.participants.append(
                    {'name': new_name, 'color': new_color, 'age': new_age}
                )
                st.rerun()

    st.subheader('Session Control')
    if st.button('Start New Session'):
        _clear_session_state()
        st.rerun()

    if st.button('End & Save Session'):
        if 'session_logger' not in st.session_state:
            st.warning('No active session to save.')
        else:
            file_path = st.session_state.session_logger.save(
                frame_memory=st.session_state.frame_memory
            )
            st.success(f'Session saved to {file_path}')
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
            config=config,
            verbosity=selected_verbosity,
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
