"""Streamlit user interface for Agentic Kayo."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import streamlit as st

from src.agent.orchestrator import run_kayo
from src.config_loader import get_configs, load_user_info
from src.voices.stt import GROQ_WHISPER_MODEL, transcribe_audio
from src.voices.tts import text_to_speech

logger = logging.getLogger(__name__)


def init_session_state() -> None:
    """Initialize session state variables for conversation and settings."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "voice_enabled" not in st.session_state:
        st.session_state.voice_enabled = True

    if "review_voice" not in st.session_state:
        st.session_state.review_voice = False

    if "last_processed_audio_hash" not in st.session_state:
        st.session_state.last_processed_audio_hash = None

    if "pending_transcript" not in st.session_state:
        st.session_state.pending_transcript = None


def render_sidebar(configs: dict[str, Any], user_info: dict[str, Any]) -> None:
    """Render sidebar controls, assistant status, and preferences."""
    with st.sidebar:
        st.title("🤖 Kayo Assistant")
        st.caption("Voice-enabled Personal AI Agent")
        st.divider()

        st.subheader("Voice Settings")
        st.session_state.voice_enabled = st.toggle(
            "🔊 Voice Responses (Edge TTS)",
            value=st.session_state.voice_enabled,
            help="When enabled, Kayo's responses will be voiced using Edge TTS.",
        )

        st.session_state.review_voice = st.toggle(
            "📝 Review Voice Transcripts",
            value=st.session_state.review_voice,
            help="When enabled, allows you to review and edit recognized speech before submitting it to Kayo.",
        )

        st.divider()

        st.subheader("System Status")
        st.caption(f"**User:** {user_info.get('name', 'User')}")
        st.caption(f"**LLM Model:** `{configs.get('model', 'Unknown')}`")
        st.caption(f"**STT Model:** `{GROQ_WHISPER_MODEL}` (Groq)")
        st.caption(f"**Tool Steps Limit:** `{configs.get('max_agent_steps', 12)}`")

        if not configs.get("groq_api_key"):
            st.warning("⚠️ `GROQ_API_KEY` is not set. Add it to `.env` or Streamlit Secrets for voice transcription.")

        st.divider()

        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending_transcript = None
            st.session_state.last_processed_audio_hash = None
            st.rerun()


def handle_user_submission(user_text: str) -> None:
    """Process user query through the Kayo agent and generate TTS if enabled."""
    clean_text = user_text.strip()
    if not clean_text:
        return

    # Add user message to conversation history
    st.session_state.messages.append({
        "role": "user",
        "content": clean_text,
        "audio": None,
    })

    # Invoke existing Kayo agent
    with st.spinner("Kayo is processing your request..."):
        try:
            response_text = run_kayo(clean_text)
        except Exception as exc:
            logger.error("Agent execution failed: %s", exc)
            response_text = f"An error occurred while executing the request: {exc}"

    # Generate speech if voice responses are enabled
    audio_bytes = None
    if st.session_state.voice_enabled and response_text:
        with st.spinner("Synthesizing voice response..."):
            audio_bytes = text_to_speech(response_text)

    # Add assistant response to history
    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "audio": audio_bytes,
    })


def render_app() -> None:
    """Main Streamlit application entrypoint."""
    st.set_page_config(
        page_title="Kayo — Voice AI Assistant",
        page_icon="🤖",
        layout="wide",
    )

    init_session_state()

    configs = get_configs()
    user_info = load_user_info()

    render_sidebar(configs, user_info)

    st.header("🤖 Kayo — Voice & Text Interface")
    st.caption("Ask questions, perform research, run calculations, and interact via voice or text.")

    # 1. Render existing conversation history
    for idx, msg in enumerate(st.session_state.messages):
        role = msg["role"]
        content = msg["content"]
        audio_data = msg.get("audio")

        with st.chat_message(role):
            st.markdown(content)
            if audio_data:
                st.audio(audio_data, format="audio/mp3")
            elif role == "assistant" and content:
                # Provide on-demand speech button if voice was disabled or failed
                if st.button("🔊 Play Voice", key=f"play_tts_{idx}"):
                    with st.spinner("Generating speech..."):
                        generated_audio = text_to_speech(content)
                        if generated_audio:
                            msg["audio"] = generated_audio
                            st.rerun()
                        else:
                            st.warning("Voice synthesis currently unavailable.")

    # 2. Browser Microphone Input (Groq Whisper STT)
    st.write("---")
    recorded_audio = st.audio_input("🎙️ Record Voice Message", key="browser_mic_input")

    if recorded_audio is not None:
        raw_bytes = recorded_audio.getvalue()
        audio_hash = hashlib.sha256(raw_bytes).hexdigest()

        # Prevent duplicate execution on Streamlit reruns
        if st.session_state.last_processed_audio_hash != audio_hash:
            st.session_state.last_processed_audio_hash = audio_hash

            if not configs.get("groq_api_key"):
                st.error("GROQ_API_KEY is missing. Please set it in `.env` or Streamlit Secrets to transcribe voice.")
            else:
                with st.spinner("Transcribing speech with Groq Whisper..."):
                    transcript = transcribe_audio(raw_bytes)

                if transcript:
                    if st.session_state.review_voice:
                        st.session_state.pending_transcript = transcript
                    else:
                        handle_user_submission(transcript)
                        st.rerun()
                else:
                    st.warning("No speech detected or recognized in the recording. Please try again.")

    # 3. Review Box for Voice Transcription (if review mode is active)
    if st.session_state.pending_transcript:
        st.info("🎙️ **Review Speech Transcription**")
        review_col, action_col1, action_col2 = st.columns([6, 1, 1])

        with review_col:
            confirmed_text = st.text_input(
                "Review/edit transcribed speech before sending:",
                value=st.session_state.pending_transcript,
                key="transcript_edit_field",
                label_visibility="collapsed",
            )

        with action_col1:
            if st.button("Send 🚀", key="send_reviewed_btn", type="primary", use_container_width=True):
                transcript_to_send = confirmed_text.strip()
                st.session_state.pending_transcript = None
                if transcript_to_send:
                    handle_user_submission(transcript_to_send)
                st.rerun()

        with action_col2:
            if st.button("Discard ❌", key="discard_reviewed_btn", use_container_width=True):
                st.session_state.pending_transcript = None
                st.rerun()

    # 4. Standard Text Chat Input
    text_prompt = st.chat_input("Type your message to Kayo...")
    if text_prompt:
        handle_user_submission(text_prompt)
        st.rerun()
