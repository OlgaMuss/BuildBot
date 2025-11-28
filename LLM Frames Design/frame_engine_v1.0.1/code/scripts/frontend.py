"""The main Streamlit application for interacting with the Frame Engine.

This script provides a web-based user interface for configuring and running the
"Mnemonic Co-Creator Marty" frame. It allows users to define the learning
context, select a speaker, and engage in a real-time chat with the AI.
"""
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any
import asyncio

import streamlit as st
import yaml

# --- Environment Setup ---
# This setup is a bit more robust for Streamlit, which runs from a different context.
script_dir = Path(__file__).parent.resolve()  # .../code/scripts/
code_dir = script_dir.parent  # .../code/
project_root = code_dir.parent  # .../frame_engine_v1.0.1/
package_path = code_dir / 'src'

if str(package_path) not in sys.path:
    sys.path.insert(0, str(package_path))

# We'll re-import everything inside functions to ensure the path is set.
from backend.frame_engine.engine import FrameEngine
from backend.frame_engine.llm import get_llm_client
from backend.frames.marty import MnemonicCoCreatorFrame
from backend.frames.answer_checker import AnswerCheckerFrame
from backend.frames.age_checker import AgeCheckerFrame
from backend.frames.policy_checker import PolicyCheckerFrame

# --- Config and Logging ---
def load_config() -> Dict[str, Any]:
    """Loads the main configuration from the `config.yaml` file."""
    config_path = script_dir / "config.yaml"
    if not config_path.is_file():
        # Use st.error for user-facing errors in the UI
        st.error(f"Configuration file not found at {config_path}")
        return {}
    with config_path.open("r") as f:
        return yaml.safe_load(f)

config = load_config()
log_level = config.get("log_level", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout, # Direct logs to stdout for Streamlit compatibility
)


# --- Page Configuration ---
st.set_page_config(
    page_title="Marty Mnemonic Co-Creator",
    page_icon="🤖"
)

st.title("🤖 Marty Mnemonic Co-Creator")

# --- Session State Initialization ---
if "participants" not in st.session_state:
    # Default participants for the first run
    st.session_state.participants = [
        {"name": "Red", "color": "#FF4B4B", "age": 14},
        {"name": "Green", "color": "#2BCB54", "age": 15},
        {"name": "Blue", "color": "#4B7EFF", "age": 14},
    ]

# --- Sidebar for Configuration ---
with st.sidebar:
    st.header("Configuration")
    
    # Load .env variables
    try:
        from dotenv import load_dotenv

        # Construct the path to the .env file located in the same directory as the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dotenv_path = os.path.join(script_dir, ".env")

        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path=dotenv_path)
        else:
            st.warning("'.env' file not found. Please make sure it exists in the 'scripts' directory.")

        openai_api_key = os.getenv("OPENAI_API_KEY")
    except ImportError:
        st.warning("`python-dotenv` not installed. Cannot load .env file.")

    with st.expander("Learning Experience", expanded=False):
        topic = st.text_input("Topic", "Microcontrollers")
        # Load learning material from the Markdown file
        try:
            with open(project_root / "microcontrollers.md", "r") as f:
                default_learning_material = f.read()
        except FileNotFoundError:
            default_learning_material = """A microcontroller is a compact integrated circuit designed to govern a specific operation in an embedded system.\nKey components include:\n1.  CPU (Central Processing Unit): The 'brain' that executes instructions.\n2.  Memory: Flash (Program Memory) and RAM (Data Memory).\n3.  Peripherals (I/O): GPIO, ADC, Communication Interfaces, Timers.\nAn example is the ESP32, which also includes built-in Wi-Fi and Bluetooth.\n"""

        learning_material = st.text_area(
            "Learning Material",
            default_learning_material,
            height=250
        )
        mnemonic_type = st.selectbox("Mnemonic Type", ["Story", "Acronym", "Song"])

    st.subheader("Participants")
    
    # Display current participants and remove button
    for i, p in enumerate(st.session_state.participants):
        cols = st.columns([0.5, 0.3, 0.2])
        cols[0].write(f"**{p['name']}**")
        cols[1].write(f"Age: {p['age']}")
        if cols[2].button("X", key=f"remove_{i}"):
            st.session_state.participants.pop(i)
            st.rerun()

    # Form to add a new participant
    with st.form("new_participant_form"):
        st.write("Add New Participant:")
        cols = st.columns([0.5, 0.3, 0.2])
        new_name = cols[0].text_input("Name", label_visibility="collapsed")
        new_color = cols[1].color_picker("Color", label_visibility="collapsed")
        new_age = cols[2].number_input("Age", min_value=5, max_value=99, value=14, label_visibility="collapsed")
        
        if st.form_submit_button("Add"):
            if new_name:
                st.session_state.participants.append(
                    {"name": new_name, "color": new_color, "age": new_age}
                )
                st.rerun()

    st.subheader("Session Control")
    if st.button("Start New Session"):
        # Clear the state to start fresh and rerun the script
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

    if st.button("End & Save Session"):
        if "engine" in st.session_state:
            if st.session_state.get("final_context") is None:
                st.warning("No conversation turns to save. Please have at least one interaction before saving.")
            else:
                async def save_session_async():
                    """Asynchronous wrapper to call the save_session method."""
                    marty_frame = st.session_state.engine.get_frame("mnemonic_co_creator_marty")
                    if marty_frame:
                        final_context = st.session_state.final_context
                        st.info("Saving session data...")
                        await marty_frame.save_session(final_context)
                        st.success("Session data saved.")
                    else:
                        st.error("Could not find Marty frame to save.")

                # Run the async save function
                asyncio.run(save_session_async())
        else:
            st.warning("No active session to save.")

# --- Main Chat Interface ---

# Initialize state
if "engine" not in st.session_state:
    try:
        if not st.session_state.participants:
            st.error("Please add at least one participant to start a session.")
            st.stop()

        student_names = [p["name"] for p in st.session_state.participants]
        average_age = int(sum(p["age"] for p in st.session_state.participants) / len(st.session_state.participants))
        
        logging.info("Initializing new session for students: %s (Avg. Age: %d)", student_names, average_age)
        llm_client = get_llm_client(model_name=config.get("model_name"))

        # --- Frame Composition ---
        # Instantiate all the frames that will be part of the pipeline.
        marty_frame = MnemonicCoCreatorFrame(
            topic=topic,
            learning_material=learning_material,
            students=student_names,
            mnemonic_type=mnemonic_type,
            phase_config=config.get("phases", {}),
            llm_client=llm_client,
        )
        answer_checker_frame = AnswerCheckerFrame(
            learning_material=learning_material,
            llm_client=llm_client
        )
        age_checker_frame = AgeCheckerFrame(
            target_age=average_age,
            llm_client=llm_client
        )
        policy_checker_frame = PolicyCheckerFrame(
            llm_client=llm_client
        )

        # The engine runs all frames in the list. Their `validate_output`
        # methods will run in parallel.
        st.session_state.engine = FrameEngine(
            frames=[
                marty_frame,
                answer_checker_frame,
                age_checker_frame,
                policy_checker_frame
            ],
            llm_client=llm_client
        )
        st.session_state.frame_memory = {}
        st.session_state.conversation_history = []
        st.session_state.final_context = None  # Initialize final_context
        st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm Marty. Let's create a mnemonic together! What should we talk about first?"}]
        logging.info("New session initialized successfully.")
    except (ValueError, FileNotFoundError) as e:
        logging.error("Initialization failed: %s", e, exc_info=True)
        st.error(f"Initialization failed: {e}")
        st.stop()


# Display chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- User Input Section ---
student_names = [p["name"] for p in st.session_state.participants]

if student_names:
    # Create a container for the input controls at the bottom
    input_container = st.container()
    with input_container:
        col1, col2 = st.columns([1, 4])
        with col1:
            speaker = st.selectbox("Speaker", options=student_names, label_visibility="collapsed")
        with col2:
            user_input_text = st.chat_input("What would you like to say to Marty?", key="user_input")

    # Accept user input
    if user_input_text and speaker:
        # Prepend speaker to the message
        formatted_input = f"{speaker}: {user_input_text}"

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": formatted_input})
        with st.chat_message("user"):
            st.markdown(formatted_input)

        # Get response from the Frame Engine
        with st.chat_message("assistant"):
            with st.spinner("Marty is thinking..."):
                engine = st.session_state.engine
                
                # Bridge from synchronous Streamlit to our async engine
                result = asyncio.run(engine.ainvoke(
                    user_input=formatted_input,
                    conversation_history=st.session_state.get("conversation_history", []),
                    frame_memory=st.session_state.get("frame_memory", {}),
                ))

                response = result["response"]

                # Update state for the next turn
                st.session_state.frame_memory = result["final_state"]["frame_memory"]
                st.session_state.conversation_history = result["final_state"]["conversation_history"]
                # Store the complete final_state (FrameContext) for session saving
                st.session_state.final_context = result["final_state"]
                
                st.markdown(response)
        
        # Add assistant response to chat history for display
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Rerun the script to immediately display the new messages and clear the
        # input box. This is a standard pattern in Streamlit chat apps.
        st.rerun()
else:
    st.warning("Session paused. Please add a participant in the sidebar to continue.")
