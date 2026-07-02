"""
Prompt Doctor — Streamlit Application
A five-level prompt engineering ladder where an AI examiner grades your prompts.

Left panel: domain picker, level tracker, task description, prompt editor.
Right panel: examiner verdict (✓/✗ per principle), live model output, revision loop.
"""

import streamlit as st
import json
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from levels import LEVELS, get_level, get_max_level, get_principles_for_level
from runner import run_student_prompt
from examiner import grade_prompt, build_fallback_verdict

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="Prompt Doctor",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Styling ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ── Root / Global ── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #e2e8f0;
    }
    .stApp {
        background: radial-gradient(ellipse at 20% 50%, #0f172a 0%, #020617 100%);
    }
    /* Animated background particles */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background:
            radial-gradient(2px 2px at 15% 25%, rgba(99, 102, 241, 0.3), transparent),
            radial-gradient(2px 2px at 35% 55%, rgba(139, 92, 246, 0.25), transparent),
            radial-gradient(2px 2px at 55% 15%, rgba(99, 102, 241, 0.2), transparent),
            radial-gradient(2px 2px at 75% 65%, rgba(139, 92, 246, 0.3), transparent),
            radial-gradient(2px 2px at 90% 35%, rgba(99, 102, 241, 0.2), transparent),
            radial-gradient(1px 1px at 5% 80%, rgba(168, 85, 247, 0.2), transparent),
            radial-gradient(1px 1px at 45% 85%, rgba(168, 85, 247, 0.15), transparent),
            radial-gradient(1px 1px at 65% 45%, rgba(99, 102, 241, 0.2), transparent),
            radial-gradient(2px 2px at 25% 70%, rgba(139, 92, 246, 0.2), transparent),
            radial-gradient(1px 1px at 80% 90%, rgba(168, 85, 247, 0.15), transparent);
        pointer-events: none;
        z-index: 0;
    }

    /* ── Main Container ── */
    .main > div {
        padding: 0 0.5rem;
        position: relative;
        z-index: 1;
    }
    .block-container {
        max-width: 1400px !important;
        padding-top: 0.75rem !important;
        padding-bottom: 2rem !important;
        background: transparent !important;
    }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar {
        width: 6px; height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #1e293b;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb {
        background: #475569;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #6366f1;
    }

    /* ── Glass Card Mixin ── */
    .glass-card {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(16px) saturate(180%);
        -webkit-backdrop-filter: blur(16px) saturate(180%);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 16px;
        padding: 1.25rem;
        transition: all 0.3s ease;
    }
    .glass-card:hover {
        border-color: rgba(99, 102, 241, 0.25);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    /* ── Header ── */
    .app-header {
        text-align: center;
        padding: 1.25rem 0 1rem 0;
        margin-bottom: 1.5rem;
        position: relative;
    }
    .app-header::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 180px;
        height: 2px;
        background: linear-gradient(90deg, transparent, #6366f1, #a855f7, #6366f1, transparent);
        border-radius: 2px;
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
    }
    .app-header h1 {
        font-size: 2.6rem;
        margin: 0;
        background: linear-gradient(135deg, #e2e8f0, #a5b4fc, #c4b5fd);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 800;
        letter-spacing: -0.5px;
        text-shadow: 0 0 40px rgba(99, 102, 241, 0.15);
    }
    .app-header p {
        font-size: 1rem;
        color: #94a3b8;
        margin: 0.4rem 0 0 0;
        font-weight: 400;
    }

    /* ── Level Badges ── */
    .level-badge {
        display: inline-block;
        padding: 0.35rem 1rem;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        letter-spacing: 0.3px;
        border: 1px solid transparent;
    }
    .level-badge.locked {
        background: rgba(51, 65, 85, 0.5);
        color: #64748b;
        border-color: rgba(71, 85, 105, 0.3);
    }
    .level-badge.completed {
        background: linear-gradient(135deg, rgba(5, 150, 105, 0.25), rgba(16, 185, 129, 0.15));
        color: #34d399;
        border-color: rgba(52, 211, 153, 0.3);
        box-shadow: 0 0 20px rgba(52, 211, 153, 0.1);
    }
    .level-badge.current {
        background: linear-gradient(135deg, rgba(217, 119, 6, 0.25), rgba(245, 158, 11, 0.15));
        color: #fbbf24;
        border-color: rgba(251, 191, 36, 0.3);
        box-shadow: 0 0 20px rgba(251, 191, 36, 0.15);
        animation: pulse 2s infinite;
    }

    @keyframes pulse {
        0% { box-shadow: 0 0 20px rgba(251, 191, 36, 0.15); }
        50% { box-shadow: 0 0 40px rgba(251, 191, 36, 0.3); }
        100% { box-shadow: 0 0 20px rgba(251, 191, 36, 0.15); }
    }

    /* ── Panels ── */
    .left-panel {
        padding-right: 1rem;
        border-right: 1px solid rgba(148, 163, 184, 0.1);
        min-height: 600px;
    }
    .right-panel {
        padding-left: 1rem;
        min-height: 600px;
    }
    @media (max-width: 768px) {
        .left-panel { border-right: none; padding-right: 0; }
        .right-panel { padding-left: 0; }
    }

    /* ── Section styling (no card needed, glass is applied inline) ── */

    /* ── Verdict Panel ── */
    .principle-pass {
        color: #34d399;
        font-weight: 700;
    }
    .principle-fail {
        color: #f87171;
        font-weight: 700;
    }
    .principle-block {
        border-left: 4px solid rgba(148, 163, 184, 0.2);
        padding: 0.7rem 1rem;
        margin: 0.6rem 0;
        border-radius: 0 12px 12px 0;
        background: rgba(30, 41, 59, 0.4);
        transition: all 0.2s;
        backdrop-filter: blur(4px);
    }
    .principle-block.pass {
        border-left-color: #10b981;
        background: rgba(5, 150, 105, 0.1);
    }
    .principle-block.fail {
        border-left-color: #ef4444;
        background: rgba(239, 68, 68, 0.1);
    }

    /* ── Verdict banners ── */
    .verdict-pass {
        background: linear-gradient(135deg, rgba(5, 150, 105, 0.3), rgba(16, 185, 129, 0.15));
        backdrop-filter: blur(12px);
        border: 1px solid rgba(52, 211, 153, 0.25);
        color: #6ee7b7;
        padding: 1.2rem;
        border-radius: 16px;
        text-align: center;
        font-size: 1.15rem;
        font-weight: 700;
        margin: 1rem 0;
        box-shadow: 0 0 30px rgba(52, 211, 153, 0.1);
        letter-spacing: 0.3px;
    }
    .verdict-revise {
        background: linear-gradient(135deg, rgba(217, 119, 6, 0.3), rgba(245, 158, 11, 0.15));
        backdrop-filter: blur(12px);
        border: 1px solid rgba(251, 191, 36, 0.25);
        color: #fcd34d;
        padding: 1.2rem;
        border-radius: 16px;
        text-align: center;
        font-size: 1.15rem;
        font-weight: 700;
        margin: 1rem 0;
        box-shadow: 0 0 30px rgba(251, 191, 36, 0.1);
        letter-spacing: 0.3px;
    }

    /* ── Output Area ── */
    .output-area {
        background: rgba(15, 23, 42, 0.9);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(148, 163, 184, 0.1);
        color: #cbd5e1;
        padding: 1.2rem;
        border-radius: 12px;
        font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Courier New', monospace;
        font-size: 0.82rem;
        line-height: 1.6;
        white-space: pre-wrap;
        overflow-x: auto;
        max-height: 420px;
        overflow-y: auto;
    }

    /* ── Reasoning Box ── */
    .reasoning-box {
        background: rgba(217, 119, 6, 0.08);
        backdrop-filter: blur(4px);
        border-left: 4px solid #f59e0b;
        padding: 0.9rem 1.1rem;
        border-radius: 0 12px 12px 0;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        line-height: 1.6;
        color: #fde68a;
    }
    .reasoning-box summary {
        font-weight: 600;
        cursor: pointer;
        color: #fbbf24;
    }

    /* ── Error Box ── */
    .error-box {
        background: rgba(239, 68, 68, 0.1);
        backdrop-filter: blur(4px);
        border: 1px solid rgba(239, 68, 68, 0.25);
        padding: 0.9rem 1.1rem;
        border-radius: 12px;
        color: #fca5a5;
        margin: 0.5rem 0;
        font-weight: 500;
    }

    /* ── Button Styling ── */
    .stButton > button {
        width: 100%;
        border-radius: 12px;
        font-weight: 600;
        padding: 0.6rem 1rem;
        font-family: 'Inter', sans-serif;
        transition: all 0.25s ease;
        border: none;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        color: white !important;
        box-shadow: 0 4px 16px rgba(79, 70, 229, 0.25);
    }
    .stButton > button[kind="primary"]:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: 0 6px 24px rgba(79, 70, 229, 0.35);
    }
    .stButton > button[kind="primary"]:disabled {
        opacity: 0.35;
        background: rgba(71, 85, 105, 0.5) !important;
        box-shadow: none;
    }
    .stButton > button:not([kind]) {
        background: rgba(51, 65, 85, 0.4);
        color: #94a3b8;
        border: 1px solid rgba(148, 163, 184, 0.15);
        backdrop-filter: blur(4px);
    }
    .stButton > button:not([kind]):hover {
        background: rgba(71, 85, 105, 0.5);
        border-color: rgba(148, 163, 184, 0.3);
    }

    /* ── Text Area ── */
    .stTextArea textarea {
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        font-size: 0.88rem;
        border: 1.5px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        padding: 0.75rem;
        background: rgba(15, 23, 42, 0.7);
        color: #e2e8f0;
        transition: border-color 0.2s, box-shadow 0.2s;
        line-height: 1.5;
        backdrop-filter: blur(4px);
    }
    .stTextArea textarea:focus {
        border-color: #6366f1;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15), 0 0 20px rgba(99, 102, 241, 0.05);
        background: rgba(15, 23, 42, 0.85);
    }
    .stTextArea textarea::placeholder {
        color: #475569;
    }

    /* ── Selectbox ── */
    .stSelectbox > div > div {
        border-radius: 12px;
        border: 1.5px solid rgba(148, 163, 184, 0.2);
        font-family: 'Inter', sans-serif;
        background: rgba(30, 41, 59, 0.6) !important;
        backdrop-filter: blur(4px);
        color: #e2e8f0 !important;
    }
    .stSelectbox > div > div:hover {
        border-color: rgba(99, 102, 241, 0.4);
    }
    .stSelectbox > div > div:focus-within {
        border-color: #6366f1;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
    }
    /* Dropdown menu */
    div[data-baseweb="select"] > div {
        background: rgba(30, 41, 59, 0.95) !important;
        backdrop-filter: blur(16px);
        border: 1px solid rgba(148, 163, 184, 0.15);
    }
    div[data-baseweb="select"] li {
        color: #e2e8f0 !important;
    }
    div[data-baseweb="select"] li:hover {
        background: rgba(99, 102, 241, 0.2) !important;
    }

    /* ── Expander ── */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #94a3b8;
        border-radius: 10px;
        background: rgba(30, 41, 59, 0.4) !important;
        font-family: 'Inter', sans-serif;
        border: 1px solid rgba(148, 163, 184, 0.08);
        backdrop-filter: blur(4px);
        transition: all 0.2s;
    }
    .streamlit-expanderHeader:hover {
        background: rgba(51, 65, 85, 0.5) !important;
        border-color: rgba(99, 102, 241, 0.2);
    }
    .streamlit-expanderContent {
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-top: none;
        border-radius: 0 0 10px 10px;
        padding: 0.75rem !important;
        background: rgba(15, 23, 42, 0.5);
        backdrop-filter: blur(4px);
    }

    /* ── Info / Success / Warning boxes ── */
    .stAlert {
        border-radius: 12px;
        border: none;
        font-family: 'Inter', sans-serif;
        backdrop-filter: blur(8px);
    }
    .stInfo {
        background: rgba(59, 130, 246, 0.12) !important;
        border: 1px solid rgba(59, 130, 246, 0.2);
        color: #93c5fd !important;
    }
    .stSuccess {
        background: rgba(34, 197, 94, 0.12) !important;
        border: 1px solid rgba(34, 197, 94, 0.2);
        color: #86efac !important;
    }
    .stWarning {
        background: rgba(234, 179, 8, 0.12) !important;
        border: 1px solid rgba(234, 179, 8, 0.2);
        color: #fde047 !important;
    }
    .stError {
        background: rgba(239, 68, 68, 0.12) !important;
        border: 1px solid rgba(239, 68, 68, 0.2);
        color: #fca5a5 !important;
    }

    /* ── Caption / Meta text ── */
    .caption-text {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 0.5rem;
    }

    /* ── Divider ── */
    hr {
        margin: 1.25rem 0;
        border: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.15), transparent);
    }

    /* ── Sample Input ── */
    .sample-input-box {
        background: rgba(30, 41, 59, 0.5);
        padding: 0.9rem 1.1rem;
        border-radius: 12px;
        font-style: italic;
        color: #94a3b8;
        border: 1px solid rgba(148, 163, 184, 0.1);
        line-height: 1.5;
        backdrop-filter: blur(4px);
    }

    /* ── Labels / Headers in dark theme ── */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #f1f5f9 !important;
    }
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: #e2e8f0 !important;
    }
    .stMarkdown p, .stMarkdown li {
        color: #cbd5e1;
    }
    .stMarkdown strong {
        color: #e2e8f0;
    }

    /* ── Spinner ── */
    .stSpinner > div {
        border-top-color: #6366f1 !important;
        border-right-color: rgba(99, 102, 241, 0.3) !important;
        border-bottom-color: rgba(99, 102, 241, 0.1) !important;
        border-left-color: rgba(99, 102, 241, 0.1) !important;
    }

    /* ── Metric / Data display ── */
    .stMetric label, .stMetric [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
    }

    /* ── Code blocks inside markdown ── */
    code {
        background: rgba(30, 41, 59, 0.7) !important;
        color: #a5b4fc !important;
        padding: 0.15em 0.4em;
        border-radius: 6px;
        font-size: 0.85em;
    }

    /* ── Sidebar (collapsed but visible) ── */
    .css-1rs6os, .css-1d391kg, [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.95) !important;
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(148, 163, 184, 0.1);
    }
</style>
""", unsafe_allow_html=True)


# ─── Constants ────────────────────────────────────────────────────────────

DOMAINS = [
    "Customer Support",
    "Legal / Compliance",
    "Healthcare",
    "Education / Tutoring",
    "Financial Advisory",
    "Technical Writing",
    "Creative Writing",
    "Data Analysis",
    "Project Management",
    "Custom (your own domain)"
]

DEFAULT_PROMPTS = {
    1: "You are a helpful assistant. Please respond to the following customer inquiry.",
    2: "You are a helpful assistant. Please respond to the following in a structured format.",
    3: "You are a helpful assistant. Please classify the following messages.",
    4: "You are a helpful assistant. Please solve the following problem step by step.",
    5: "You are a helpful assistant. Please respond to the following."
}


# ─── Session State ────────────────────────────────────────────────────────

def init_session_state():
    """Initialize all session state variables."""
    if "current_level" not in st.session_state:
        st.session_state.current_level = 1
    if "cleared_levels" not in st.session_state:
        st.session_state.cleared_levels = set()
    if "student_prompt" not in st.session_state:
        st.session_state.student_prompt = ""
    if "last_verdict" not in st.session_state:
        st.session_state.last_verdict = None
    if "last_live_output" not in st.session_state:
        st.session_state.last_live_output = None
    if "last_raw_response" not in st.session_state:
        st.session_state.last_raw_response = None
    if "submitted" not in st.session_state:
        st.session_state.submitted = False
    if "domain" not in st.session_state:
        st.session_state.domain = "Customer Support"
    if "evaluating" not in st.session_state:
        st.session_state.evaluating = False
    if "error" not in st.session_state:
        st.session_state.error = None
    if "show_reasoning" not in st.session_state:
        st.session_state.show_reasoning = True
    if "revision_count" not in st.session_state:
        st.session_state.revision_count = 0
    if "level_revisions" not in st.session_state:
        st.session_state.level_revisions = {}


def reset_for_new_level(level_num):
    """Reset state when moving to a new level."""
    st.session_state.current_level = level_num
    st.session_state.student_prompt = ""
    st.session_state.last_verdict = None
    st.session_state.last_live_output = None
    st.session_state.last_raw_response = None
    st.session_state.submitted = False
    st.session_state.error = None
    st.session_state.revision_count = 0
    if level_num not in st.session_state.level_revisions:
        st.session_state.level_revisions[level_num] = 0


# ─── Helper Functions ────────────────────────────────────────────────────

def render_level_tracker():
    """Render the level progression tracker at the top."""
    max_level = get_max_level()
    cleared = st.session_state.cleared_levels
    current = st.session_state.current_level
    
    cols = st.columns(max_level)
    for i in range(1, max_level + 1):
        level = get_level(i)
        with cols[i - 1]:
            if i in cleared:
                badge_class = "completed"
                label = f"✓ L{i}"
            elif i == current:
                badge_class = "current"
                label = f"▶ L{i}"
            elif i < current and i not in cleared:
                badge_class = "locked"
                label = f"🔒 L{i}"
            elif i > current:
                badge_class = "locked"
                label = f"🔒 L{i}"
            else:
                badge_class = "locked"
                label = f"L{i}"
            
            st.markdown(
                f'<div class="level-badge {badge_class}" '
                f'title="{level["name"]}: {level["description"]}">{label}</div>',
                unsafe_allow_html=True
            )
            st.caption(level["name"])


def render_verdict_panel(verdict: dict):
    """Render the examiner's verdict with ✓/✗ per principle."""
    if not verdict or "principles" not in verdict:
        return
    
    principles = verdict["principles"]
    all_pass = all(p.get("pass", False) for p in principles)
    
    # Verdict banner
    if verdict.get("verdict") == "pass" or all_pass:
        st.markdown('<div class="verdict-pass">✅ PASS — All principles satisfied! '
                   f'Level {verdict.get("level", "?")} cleared.</div>',
                   unsafe_allow_html=True)
    else:
        fail_count = sum(1 for p in principles if not p.get("pass", False))
        st.markdown(f'<div class="verdict-revise">🔄 REVISE — {fail_count} principle(s) '
                   f'need attention. Keep refining your prompt.</div>',
                   unsafe_allow_html=True)
    
    # Per-principle breakdown
    st.markdown("### 📋 Principle-by-Principle Assessment")
    for principle in principles:
        name = principle.get("name", "unknown")
        passed = principle.get("pass", False)
        weakness = principle.get("weakness", "")
        question = principle.get("question", "")
        
        if passed:
            icon = "✅"
            status_class = "pass"
            status_text = "PASS"
        else:
            icon = "❌"
            status_class = "fail"
            status_text = "FAIL"
        
        # Get the human-readable description
        level_def = get_level(verdict.get("level", 1))
        desc = ""
        if level_def and "principle_descriptions" in level_def:
            desc = level_def["principle_descriptions"].get(name, "")
        
        st.markdown(
            f'<div class="principle-block {status_class}">'
            f'<div><span class="principle-{status_class}">{icon} {status_text}</span> '
            f'<strong>{name.replace("_", " ").title()}</strong></div>'
            f'<div style="font-size:0.85rem;color:#666;margin-top:0.25rem;">{desc}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
        
        if not passed and weakness:
            st.markdown(
                f'<div style="padding:0 0.75rem;margin-bottom:0.25rem;">'
                f'<strong>🔍 Weakness:</strong> <em>"{weakness}"</em></div>',
                unsafe_allow_html=True
            )
        
        if not passed and question:
            st.markdown(
                f'<div style="padding:0 0.75rem;margin-bottom:0.5rem;">'
                f'<strong>💡 Question:</strong> {question}</div>',
                unsafe_allow_html=True
            )
    
    # Show raw examiner reasoning (collapsible)
    raw = st.session_state.last_raw_response
    if raw:
        # Try to extract reasoning from <reasoning> tags
        import re
        reasoning_match = re.search(r'<reasoning>([\s\S]*?)</reasoning>', raw)
        reasoning_text = reasoning_match.group(1).strip() if reasoning_match else None
        
        if reasoning_text:
            with st.expander("🧠 Examiner's Reasoning", expanded=st.session_state.show_reasoning):
                st.markdown(
                    f'<div class="reasoning-box">{reasoning_text}</div>',
                    unsafe_allow_html=True
                )
        else:
            with st.expander("📄 Raw Examiner Response", expanded=False):
                st.text(raw)


def render_live_output(output: str):
    """Render the live output from running the student's prompt."""
    st.markdown("### 📤 Live Model Output")
    if output:
        st.markdown(
            f'<div class="output-area">{output}</div>',
            unsafe_allow_html=True
        )
    else:
        st.info("Submit your prompt to see the live output here.")


# ─── Main App Layout ──────────────────────────────────────────────────────

def main():
    init_session_state()
    
    # ── Header ──
    st.markdown(
        '<div class="app-header">'
        '<h1>🏥 Prompt Doctor</h1>'
        '<p>Write a prompt. The AI examiner grades it. Revise. Level up. '
        '<span style="color:#FF9800;">Five techniques, one afternoon, earned the hard way.</span></p>'
        '</div>',
        unsafe_allow_html=True
    )
    
    # ── Level Tracker ──
    render_level_tracker()
    st.markdown("---")
    
    # ── Two-Panel Layout ──
    left_col, right_col = st.columns([1, 1], gap="large")
    
    # ═══════════════════════════════════════════════════════════
    # LEFT PANEL: Domain picker, task, prompt editor
    # ═══════════════════════════════════════════════════════════
    with left_col:
    #    st.markdown('<div class="left-panel">', unsafe_allow_html=True)
        
        # Domain selection
        st.markdown("### 🌐 Pick Your Domain")
        domain_idx = DOMAINS.index(st.session_state.domain) if st.session_state.domain in DOMAINS else 0
        selected_domain = st.selectbox(
            "Choose a domain for your prompts",
            options=DOMAINS,
            index=domain_idx,
            label_visibility="collapsed",
            key="domain_selector"
        )
        
        if selected_domain != st.session_state.domain:
            st.session_state.domain = selected_domain
            reset_for_new_level(st.session_state.current_level)
        
        st.markdown("---")
        
        # Current level info
        current_level = st.session_state.current_level
        level_def = get_level(current_level)
        
        if level_def:
            st.markdown(f"### 🎯 Level {current_level}: {level_def['name']}")
            st.markdown(f"**{level_def['description']}**")
            st.markdown(f"**Task:** {level_def['task']}")
            
            # Sample input (collapsible)
            with st.expander("📥 View Sample Input", expanded=True):
                st.markdown(
                    f'<div class="sample-input-box">{level_def["sample_input"]}</div>',
                    unsafe_allow_html=True
                )
            
            # Principles for this level
            with st.expander("📏 Principles Being Judged", expanded=False):
                principles_text = get_principles_for_level(current_level)
                st.markdown(principles_text)
            
            st.markdown("---")
            
            # Prompt editor
            st.markdown("### ✍️ Your Prompt")
            st.markdown("*Write a prompt that handles the task above. The examiner will grade it against the principles for this level.*")
            
            # Prompt text area
            prompt = st.text_area(
                "Student Prompt",
                value=st.session_state.student_prompt,
                height=250,
                placeholder="Write your prompt here...\n\nExample: You are a [role]. Your task is to...\nWhen given [input], you should...\n\nFormat your output as...",
                label_visibility="collapsed",
                key="prompt_editor"
            )
            
            # Update session state as user types
            if prompt != st.session_state.student_prompt:
                st.session_state.student_prompt = prompt
                st.session_state.submitted = False
            
            # Submit button
            col1, col2 = st.columns([3, 1])
            with col1:
                submit_disabled = not prompt.strip() or st.session_state.evaluating
                if st.button(
                    "🚀 Submit for Grading",
                    disabled=submit_disabled,
                    type="primary",
                    use_container_width=True
                ):
                    st.session_state.submitted = True
                    st.session_state.evaluating = True
                    st.session_state.error = None
                    
                    with st.spinner("Running your prompt on the sample input..."):
                        # Step 1: Run the student's prompt
                        run_result = run_student_prompt(
                            student_prompt=prompt,
                            sample_input=level_def["sample_input"]
                        )
                        
                        if run_result["success"]:
                            live_output = run_result["output"]
                            st.session_state.last_live_output = live_output
                            
                            # Step 2: Grade with the examiner
                            with st.spinner("The examiner is grading your prompt..."):
                                grade_result = grade_prompt(
                                    student_prompt=prompt,
                                    sample_input=level_def["sample_input"],
                                    live_output=live_output,
                                    level=current_level
                                )
                                
                                if grade_result["success"] and grade_result["verdict"]:
                                    st.session_state.last_verdict = grade_result["verdict"]
                                    st.session_state.last_raw_response = grade_result["raw_response"]
                                    
                                    # Increment revision count
                                    st.session_state.revision_count += 1
                                    if current_level not in st.session_state.level_revisions:
                                        st.session_state.level_revisions[current_level] = 0
                                    st.session_state.level_revisions[current_level] = st.session_state.revision_count
                                    
                                    # Check if passed
                                    all_pass = all(
                                        p.get("pass", False) 
                                        for p in grade_result["verdict"].get("principles", [])
                                    )
                                    if all_pass:
                                        st.session_state.cleared_levels.add(current_level)
                                else:
                                    st.session_state.last_verdict = build_fallback_verdict(
                                        current_level,
                                        grade_result.get("error", "Unknown examiner error")
                                    )
                                    st.session_state.last_raw_response = grade_result.get("raw_response", "")
                                    st.session_state.error = grade_result.get("error", "")
                        else:
                            st.session_state.last_live_output = ""
                            st.session_state.last_verdict = build_fallback_verdict(
                                current_level,
                                run_result.get("error", "Failed to run prompt")
                            )
                            st.session_state.error = run_result.get("error", "")
                    
                    st.session_state.evaluating = False
                    st.rerun()
            
            with col2:
                if prompt.strip():
                    st.button(
                        "🗑️ Clear",
                        on_click=lambda: st.session_state.update(
                            student_prompt="",
                            submitted=False,
                            last_verdict=None,
                            last_live_output=None
                        ),
                        use_container_width=True
                    )
            
            st.markdown("---")
            
            # Level navigation (show when current level is cleared)
            if current_level in st.session_state.cleared_levels and current_level < get_max_level():
                st.success(f"🎉 Level {current_level} passed! Ready for Level {current_level + 1}?")
                if st.button(f"▶️ Advance to Level {current_level + 1}", type="primary", use_container_width=True):
                    reset_for_new_level(current_level + 1)
                    st.rerun()
            
            # Show revision count
            if st.session_state.revision_count > 0:
                st.caption(f"📊 Revisions this level: {st.session_state.revision_count}")
            
            # Show total cleared levels
            cleared_count = len(st.session_state.cleared_levels)
            if cleared_count > 0:
                st.caption(f"🏆 Levels cleared: {cleared_count}/{get_max_level()}")
        
        #    st.markdown('</div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════
    # RIGHT PANEL: Examiner verdict + live output
    # ═══════════════════════════════════════════════════════════
    with right_col:
       # st.markdown('<div class="right-panel">', unsafe_allow_html=True)
        
        st.markdown("### 🔍 Examiner Panel")
        
        # Show any errors
        if st.session_state.error:
            st.markdown(
                f'<div class="error-box">⚠️ {st.session_state.error}</div>',
                unsafe_allow_html=True
            )
        
        # Show verdict if available
        if st.session_state.last_verdict:
            render_verdict_panel(st.session_state.last_verdict)
        else:
            st.info(
                "👈 **Write a prompt on the left** and submit it for grading. "
                "The examiner will evaluate it against the level's principles "
                "and return a per-principle verdict here."
            )
            
            st.markdown("---")
            st.markdown("### 💡 How Prompt Doctor Works")
            st.markdown("""
            1. **Choose a domain** relevant to you
            2. **Read the level's task** and sample input
            3. **Write a prompt** that handles the task
            4. **Submit** — your prompt runs on the sample input, then the examiner grades it
            5. **Read the verdict** — per-principle ✓/✗ with specific weak spots quoted
            6. **Revise** — tighten your prompt and resubmit
            7. **Advance** — pass all principles to unlock the next level
            
            **The one rule:** The examiner diagnoses but never writes the fix.  
            Every improvement comes from you — that's how the skill sticks.
            """)
        
        st.markdown("---")
        
        # Live output
        render_live_output(st.session_state.last_live_output)
        
        # Show raw examiner response if available (collapsible)
        if st.session_state.last_raw_response and not st.session_state.last_verdict:
            with st.expander("📄 Raw Examiner Response", expanded=False):
                st.text(st.session_state.last_raw_response)
        
        # Stretch goals section (collapsible)
        with st.expander("🚀 Stretch Goals", expanded=False):
            st.markdown("""
            **Optional enhancements once you've cleared levels:**
            
            - **Examiner on Trial:** Compare verdicts from two different judge models
            - **Running Scorecard:** Track which Day-2 principles each gap maps to
            - **Temperature Lab:** See your winning prompt's output at temp 0 vs 1
            - **Leaderboard:** Fewest revisions to reach Level 5 wins
            """)
        
        #    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()