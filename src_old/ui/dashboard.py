"""Streamlit dashboard and main user interface for Agentic Kayo."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from src_old.agent.context import build_initial_messages
from src_old.agent.orchestrator import AgentOrchestrator
from src_old.config import get_config
from src_old.llm.codegen import generate_code
from src_old.llm.factory import get_primary_model
from src_old.storage.user_info import load_user_info, update_profile_sender
from src_old.tools.registry import default_registry, get_tool_activity_log
from src_old.voice.microphone import process_browser_audio
from src_old.voice.tts import text_to_speech_mp3

logger = logging.getLogger(__name__)


def init_session_state() -> None:
    """Initialize Streamlit session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "langchain_messages" not in st.session_state:
        st.session_state.langchain_messages = []

    if "pending_action" not in st.session_state:
        st.session_state.pending_action = None

    if "auto_speech" not in st.session_state:
        st.session_state.auto_speech = False

    if "profile" not in st.session_state:
        st.session_state.profile = load_user_info()

    if "tts_cache" not in st.session_state:
        st.session_state.tts_cache = {}


def render_sidebar() -> None:
    """Render sidebar settings for sender identity and speech preferences."""
    st.sidebar.title("⚙️ Kayo Settings")

    profile = st.session_state.profile
    current_name = profile.get("profile", {}).get("name", "")
    current_email = profile.get("profile", {}).get("email", "")

    st.sidebar.subheader("Sender Identity")
    st.sidebar.caption("Used for outgoing emails via send_mail.")

    new_name = st.sidebar.text_input("Sender Display Name", value=current_name, key="input_sender_name")
    new_email = st.sidebar.text_input("Sender Email Address", value=current_email, key="input_sender_email")

    if st.sidebar.button("💾 Save Profile", use_container_width=True):
        updated = update_profile_sender(new_name, new_email)
        st.session_state.profile = updated
        st.sidebar.success("Profile updated successfully!")

    st.sidebar.divider()

    st.sidebar.subheader("Voice Preferences")
    speak_auto = st.sidebar.radio(
        "Speak assistant responses automatically:",
        options=["No", "Yes"],
        index=1 if st.session_state.auto_speech else 0,
        help="If Yes, responses will be voiced automatically using gTTS (requires internet).",
    )
    st.session_state.auto_speech = (speak_auto == "Yes")

    st.sidebar.divider()

    # Runtime info
    cfg = get_config()
    st.sidebar.subheader("Runtime Status")
    st.sidebar.caption(f"**Primary LLM:** `{cfg.kayo_model}`")
    st.sidebar.caption(f"**Codegen LLM:** `{cfg.codegen_model}`")
    st.sidebar.caption(f"**Timezone:** `{cfg.app_timezone}`")
    st.sidebar.caption(f"**Workspace:** `{cfg.kayo_workspace}`")

    if st.sidebar.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.langchain_messages = []
        st.session_state.pending_action = None
        st.session_state.tts_cache = {}
        st.rerun()


def handle_user_input(user_text: str) -> None:
    """Process user message through the agent orchestrator."""
    clean_text = user_text.strip()
    if not clean_text:
        return

    # Append user turn to UI messages
    st.session_state.messages.append({
        "role": "user",
        "content": clean_text,
    })

    # Prepare LangChain messages
    if not st.session_state.langchain_messages:
        st.session_state.langchain_messages = build_initial_messages(
            history=[],
            profile_data=st.session_state.profile,
        )

    from langchain_core.messages import HumanMessage
    st.session_state.langchain_messages.append(HumanMessage(content=clean_text))

    _execute_orchestrator()


def _execute_orchestrator() -> None:
    """Run orchestrator loop and handle outcomes."""
    cfg = get_config()

    try:
        model = get_primary_model(cfg)
    except Exception as exc:
        err_msg = f"Model configuration error: {exc}"
        st.session_state.messages.append({"role": "assistant", "content": err_msg, "error": True})
        return

    orchestrator = AgentOrchestrator(model=model, registry=default_registry, config=cfg)

    status_placeholder = st.empty()
    def on_step(msg: str) -> None:
        status_placeholder.info(f"⏳ {msg}")

    with st.spinner("Kayo is thinking..."):
        result = orchestrator.run(
            st.session_state.langchain_messages,
            on_step_callback=on_step,
        )

    status_placeholder.empty()

    st.session_state.langchain_messages = result.messages

    if result.requires_confirmation:
        st.session_state.pending_action = result.pending_action
        st.session_state.messages.append({
            "role": "assistant",
            "content": result.content,
            "requires_confirmation": True,
            "pending_action": result.pending_action,
        })
    else:
        st.session_state.pending_action = None
        msg_record = {
            "role": "assistant",
            "content": result.content,
            "tool_calls": result.tool_calls,
        }
        st.session_state.messages.append(msg_record)

        # Automatic speech generation if enabled
        if st.session_state.auto_speech and result.content:
            audio_bytes = text_to_speech_mp3(result.content)
            if audio_bytes:
                st.session_state.tts_cache[len(st.session_state.messages) - 1] = audio_bytes


def handle_confirmation(approved: bool) -> None:
    """Handle user response to confirmation dialog."""
    pending = st.session_state.pending_action
    if not pending:
        return

    cfg = get_config()
    try:
        model = get_primary_model(cfg)
    except Exception as exc:
        st.error(f"Error resuming agent: {exc}")
        return

    orchestrator = AgentOrchestrator(model=model, registry=default_registry, config=cfg)

    status_placeholder = st.empty()
    def on_step(msg: str) -> None:
        status_placeholder.info(f"⏳ {msg}")

    with st.spinner("Executing approved action..."):
        result = orchestrator.resume_action(
            messages=st.session_state.langchain_messages,
            pending_action=pending,
            approved=approved,
            on_step_callback=on_step,
        )

    status_placeholder.empty()
    st.session_state.langchain_messages = result.messages

    if result.requires_confirmation:
        st.session_state.pending_action = result.pending_action
        st.session_state.messages.append({
            "role": "assistant",
            "content": result.content,
            "requires_confirmation": True,
            "pending_action": result.pending_action,
        })
    else:
        st.session_state.pending_action = None
        st.session_state.messages.append({
            "role": "assistant",
            "content": result.content,
            "tool_calls": result.tool_calls,
        })
        if st.session_state.auto_speech and result.content:
            audio_bytes = text_to_speech_mp3(result.content)
            if audio_bytes:
                st.session_state.tts_cache[len(st.session_state.messages) - 1] = audio_bytes

    st.rerun()


def render_chat_tab() -> None:
    """Render the primary interactive chat interface."""
    st.subheader("💬 Chat with Kayo")

    # Display chat history
    for idx, msg in enumerate(st.session_state.messages):
        role = msg["role"]
        content = msg.get("content", "")

        with st.chat_message(role):
            st.markdown(content)

            # Render clickable links if open_website was invoked
            tool_calls = msg.get("tool_calls") or []
            for tc in tool_calls:
                if tc.get("tool") == "open_website":
                    res = tc.get("result", {}).get("result", {})
                    url = res.get("url")
                    if url:
                        st.markdown(f"🔗 **[Open Website: {url}]({url})**")

            # Show pending confirmation card
            if msg.get("requires_confirmation") and idx == len(st.session_state.messages) - 1:
                action = msg.get("pending_action", {})
                tool = action.get("tool", "")
                args = action.get("arguments", {})
                preview = action.get("preview")

                st.warning(f"⚠️ **Action Required: Confirmation for `{tool}`**")
                if preview:
                    st.write("**Email Preview:**")
                    st.json(preview)
                else:
                    st.write("**Parameters:**")
                    st.json(args)

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve & Execute", key=f"approve_{idx}", type="primary", use_container_width=True):
                        handle_confirmation(approved=True)
                with col2:
                    if st.button("❌ Cancel Action", key=f"cancel_{idx}", use_container_width=True):
                        handle_confirmation(approved=False)

            # Voice output controls for assistant messages
            if role == "assistant" and not msg.get("requires_confirmation") and content:
                cached_audio = st.session_state.tts_cache.get(idx)
                if cached_audio:
                    st.audio(cached_audio, format="audio/mp3", autoplay=st.session_state.auto_speech)
                else:
                    # Provide manual speaker button when auto-speech is off
                    if not st.session_state.auto_speech:
                        if st.button("🔊 Read Aloud", key=f"speak_{idx}"):
                            with st.spinner("Generating speech..."):
                                audio_bytes = text_to_speech_mp3(content)
                                if audio_bytes:
                                    st.session_state.tts_cache[idx] = audio_bytes
                                    st.rerun()
                                else:
                                    st.caption("⚠️ Text-to-speech currently unavailable.")

    # Voice input component (Browser microphone)
    st.write("---")
    audio_val = st.audio_input("🎙️ Record Voice Message (Vosk Offline Recognition)", key="browser_mic")
    if audio_val is not None:
        # Check if this audio has already been processed in this session
        audio_id = f"audio_{audio_val.name}_{audio_val.size}"
        if st.session_state.get("last_processed_audio") != audio_id:
            st.session_state["last_processed_audio"] = audio_id
            with st.spinner("Transcribing your voice with Vosk..."):
                transcript = process_browser_audio(audio_val)
            if transcript:
                st.success(f"Recognized: *\"{transcript}\"*")
                handle_user_input(transcript)
                st.rerun()
            else:
                st.warning("Could not transcribe any speech from recording.")

    # Chat text composer
    user_prompt = st.chat_input("Type your message to Kayo...")
    if user_prompt:
        handle_user_input(user_prompt)
        st.rerun()


def render_codegen_tab() -> None:
    """Dedicated Code Generation interface using OpenRouter model."""
    st.subheader("💻 Dedicated Code Generator")
    st.caption("Powered by the dedicated OpenRouter coding model.")

    cfg = get_config()
    st.info(f"Target Coding Model: `{cfg.codegen_model}`")

    language = st.selectbox("Programming Language", ["python", "javascript", "typescript", "bash", "go", "rust", "html/css"])
    prompt = st.text_area("Describe the code to generate:", height=150, placeholder="e.g. Write a fast thread-safe LRU cache with expiration...")
    context = st.text_area("Optional Context / Constraints:", height=80, placeholder="e.g. Must run on Python 3.13 without third-party dependencies.")

    if st.button("🚀 Generate Code", type="primary"):
        if not prompt.strip():
            st.warning("Please provide a prompt.")
            return

        with st.spinner("Generating code with OpenRouter..."):
            try:
                code_result = generate_code(
                    prompt=prompt,
                    language=language,
                    context=context if context.strip() else None,
                    config=cfg,
                )
                st.markdown("### Generated Code")
                st.code(code_result, language=language)
            except Exception as exc:
                st.error(f"Code generation failed: {exc}")


def render_tools_tab() -> None:
    """Display registered tools status and recent activity log."""
    st.subheader("🛠️ Tool System & Activity")

    specs = default_registry.list_tool_specs()
    st.write(f"Total Registered Tools: **{len(specs)}**")

    with st.expander("📋 View All Registered Tools & Schemas", expanded=False):
        for s in sorted(specs, key=lambda x: x.name):
            badge = "🔒 Gated (Requires Confirmation)" if s.requires_confirmation else "🟢 Standard"
            st.markdown(f"**`{s.name}`** — *{badge}*")
            st.caption(s.description)

    st.divider()
    st.subheader("Recent Tool Activity")
    activity = get_tool_activity_log()
    if not activity:
        st.info("No tool activity recorded yet in this session.")
    else:
        for act in reversed(activity):
            status = act.get("status")
            icon = "✅" if status == "success" else ("⚠️" if status == "requires_confirmation" else "❌")
            st.markdown(
                f"{icon} **`{act.get('tool')}`** — {status.upper()} "
                f"({act.get('duration_seconds')}s) at `{act.get('timestamp')}`"
            )


def render_dashboard() -> None:
    """Main dashboard entrypoint."""
    st.set_page_config(
        page_title="Agentic Kayo",
        page_icon="🤖",
        layout="wide",
    )

    init_session_state()
    render_sidebar()

    st.title("🤖 Agentic Kayo")
    st.caption("Voice-enabled AI assistant with bounded tool orchestration and isolated execution.")

    tab_chat, tab_codegen, tab_tools = st.tabs(["💬 Chat", "💻 Code Generator", "🛠️ Tools & Activity"])

    with tab_chat:
        render_chat_tab()

    with tab_codegen:
        render_codegen_tab()

    with tab_tools:
        render_tools_tab()
