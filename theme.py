"""theme.py - Vintage red/black/grey theme, CSS, navbar with auto-detected page paths."""
import os
import base64
import streamlit as st
from streamlit_option_menu import option_menu


THEME = {
    "bg":            "#1B1C1C",
    "card":          "#2E2D2D",
    "card2":         "#252424",
    "border":        "#444444",
    "primary":       "#8C2431",
    "primary_hover": "#A82C3C",
    "text":          "#F7EAE6",
    "muted":         "#CFC6CB",
    "faint":         "#888888",
}


_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_PAGES_DIR = os.path.join(_PROJECT_ROOT, "pages")


def _find_page(prefix_keywords):
    if not os.path.isdir(_PAGES_DIR):
        return None
    for fname in sorted(os.listdir(_PAGES_DIR)):
        if not fname.endswith(".py"):
            continue
        lower = fname.lower()
        for kw in prefix_keywords:
            if kw.lower() in lower:
                return f"pages/{fname}"
    return None


PAGE_PATHS = {
    "Homepage":                                  "home_page.py",
    "Undervalued Stock Screener":                _find_page(["screener", "undervalued"]),
    "Automated Stock Valuation and Analysis":    _find_page(["auto_valuation", "automated"]),
    "Manual Tweaks to Valuation Parameters":     _find_page(["manual", "tweaks"]),
    "Monte Carlo Simulation":                    _find_page(["monte_carlo", "montecarlo", "monte"]),
}


def inject_global_css():
    st.markdown(
        f"""
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
        <style>
            html, body, [class*="st-"] {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
                color: {THEME['text']};
            }}
            .stApp {{ background-color: {THEME['bg']}; }}

            /* === FIX FOR LITERAL ICON-NAME TEXT IN SIDEBAR COLLAPSE BUTTON === */
            /* Force Material Symbols ligature rendering on Streamlit icon spans */
            span.material-symbols-rounded,
            span.material-icons,
            [data-testid="stIconMaterial"],
            [data-testid="stSidebarCollapseButton"] span,
            [data-testid="stSidebarCollapsedControl"] span,
            button[kind="header"] span {{
                font-family: 'Material Symbols Rounded', 'Material Icons' !important;
                font-weight: normal !important;
                font-style: normal !important;
                font-size: 24px !important;
                line-height: 1 !important;
                letter-spacing: normal !important;
                text-transform: none !important;
                display: inline-block !important;
                white-space: nowrap !important;
                word-wrap: normal !important;
                direction: ltr !important;
                -webkit-font-feature-settings: 'liga' !important;
                font-feature-settings: 'liga' !important;
                -webkit-font-smoothing: antialiased !important;
                color: {THEME['text']} !important;
                width: auto !important;
                overflow: hidden !important;
                max-width: 28px !important;
            }}

            /* Hide any text node that still leaks through if the font fails to load */
            [data-testid="stSidebarCollapseButton"],
            [data-testid="stSidebarCollapsedControl"] {{
                font-size: 0 !important;
                line-height: 0 !important;
            }}
            [data-testid="stSidebarCollapseButton"] *,
            [data-testid="stSidebarCollapsedControl"] *,
            [data-testid="stSidebarCollapseButton"] svg,
            [data-testid="stSidebarCollapsedControl"] svg,
            [data-testid="stSidebarCollapseButton"] span.material-symbols-rounded,
            [data-testid="stSidebarCollapsedControl"] span.material-symbols-rounded {{
                font-size: 24px !important;
                line-height: 1 !important;
            }}

            section[data-testid="stSidebar"] {{
                background-color: {THEME['card2']};
                border-right: 1px solid {THEME['border']};
            }}
            .section-header {{
                font-size: 1.6rem; font-weight: 800; color: {THEME['text']};
                margin-top: 0.6rem; margin-bottom: 0.2rem; letter-spacing: -0.3px;
            }}
            .section-sub {{ font-size: 0.95rem; color: {THEME['muted']}; margin-bottom: 0.6rem; }}
            .divider {{ height: 1px; background: {THEME['border']}; margin: 1rem 0 1.2rem 0; }}
            .stButton > button {{
                background-color: {THEME['primary']}; color: {THEME['text']};
                border: 1px solid {THEME['border']}; border-radius: 999px;
                padding: 0.55rem 1.4rem; font-weight: 600;
                transition: transform 0.12s ease, background-color 0.12s ease;
            }}
            .stButton > button:hover {{
                background-color: {THEME['primary_hover']}; transform: scale(1.02);
                border-color: {THEME['primary_hover']}; color: {THEME['text']};
            }}
            .stButton > button:focus, .stButton > button:active {{
                background-color: {THEME['primary_hover']}; color: {THEME['text']};
                box-shadow: 0 0 0 2px {THEME['primary']}66;
            }}
            .big-explain-btn .stButton > button {{
                font-size: 1.05rem !important; font-weight: 800 !important;
                padding: 0.9rem 1.6rem !important;
                background-color: {THEME['primary']} !important;
                border: 2px solid {THEME['primary_hover']} !important; letter-spacing: 0.2px;
            }}
            .ai-mini-btn .stButton > button {{
                padding: 0.4rem 0.9rem !important; font-size: 0.85rem !important;
            }}
            div[data-testid="stMetricValue"] {{ color: {THEME['text']}; font-weight: 700; }}
            div[data-testid="stMetricLabel"] {{ color: {THEME['muted']}; }}
            .screener-table {{
                width: 100%; border-collapse: collapse;
                background: {THEME['card']}; color: {THEME['text']};
                font-size: 0.92rem; border: 1px solid {THEME['border']};
                border-radius: 10px; overflow: hidden;
            }}
            .screener-table thead tr {{
                background: {THEME['card2']}; border-bottom: 2px solid {THEME['primary']};
            }}
            .screener-table th {{
                padding: 0.7rem 0.75rem; text-align: left; font-weight: 700;
                color: {THEME['text']}; font-size: 0.85rem; letter-spacing: 0.2px;
            }}
            .screener-table td {{
                padding: 0.6rem 0.75rem; border-bottom: 1px solid {THEME['border']};
            }}
            .screener-table tbody tr:nth-child(even) {{ background: {THEME['card2']}; }}
            .screener-table tbody tr:hover {{ background: {THEME['primary']}40; }}
            .pos {{ color: #7CD992; font-weight: 600; }}
            .neg {{ color: #E07B7B; font-weight: 600; }}
            .stTabs [data-baseweb="tab-list"] {{ gap: 0.4rem; }}
            .stTabs [data-baseweb="tab"] {{
                background: {THEME['card2']}; color: {THEME['muted']};
                border-radius: 8px 8px 0 0; padding: 0.5rem 1rem;
            }}
            .stTabs [aria-selected="true"] {{
                background: {THEME['primary']}; color: {THEME['text']};
            }}
            div[data-testid="stExpander"] {{
                background: {THEME['card']}; border: 1px solid {THEME['border']};
                border-radius: 10px;
            }}
            .stProgress > div > div > div > div {{ background-color: {THEME['primary']}; }}
            input, textarea {{
                background-color: {THEME['card']} !important;
                color: {THEME['text']} !important;
                border: 1px solid {THEME['border']} !important;
            }}
            div[data-baseweb="select"] > div {{
                background-color: {THEME['card']} !important;
                color: {THEME['text']} !important;
                border: 1px solid {THEME['border']} !important;
            }}
        </style>

        <!-- JS fallback: replace any literal 'keyboard_double_arrow_*' text with proper arrow chars -->
        <script>
            (function() {{
                if (window.__icon_text_fix_attached__) return;
                window.__icon_text_fix_attached__ = true;

                function fix() {{
                    const targets = document.querySelectorAll(
                        '[data-testid="stSidebarCollapseButton"], ' +
                        '[data-testid="stSidebarCollapsedControl"], ' +
                        'button[kind="header"]'
                    );
                    targets.forEach(el => {{
                        const txt = (el.innerText || '').trim().toLowerCase();
                        if (txt.includes('keyboard_double_arrow_left') ||
                            txt.includes('keyboard_double_arrow_right') ||
                            txt.includes('keyboard_double')) {{
                            // Replace with arrow glyph
                            el.innerText = txt.includes('left') ? '\u00AB' : '\u00BB';
                            el.style.fontSize = '20px';
                            el.style.fontFamily = 'Inter, sans-serif';
                        }}
                    }});
                }}

                fix();
                const obs = new MutationObserver(fix);
                obs.observe(document.body, {{ childList: true, subtree: true }});
            }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


def render_navbar(active_label=None):
    """Render the top horizontal navbar. Auto-resolves page paths."""
    options = list(PAGE_PATHS.keys())
    icons = ["house", "search", "bar-chart", "sliders", None]

    default_idx = 0
    if active_label in options:
        default_idx = options.index(active_label)

    selected = option_menu(
        menu_title=None,
        options=options,
        icons=icons,
        orientation="horizontal",
        default_index=default_idx,
        key=f"navbar_{active_label or 'default'}",
        styles={
            "container": {
                "padding": "0.4rem 0.4rem",
                "background-color": THEME["card2"],
                "border": f"1px solid {THEME['border']}",
                "border-radius": "12px",
                "margin-bottom": "1rem",
            },
            "icon": {"color": THEME["muted"], "font-size": "0.95rem"},
            "nav-link": {
                "font-size": "0.88rem", "font-weight": "600",
                "color": THEME["muted"], "padding": "0.55rem 0.9rem",
                "border-radius": "8px", "margin": "0 0.2rem",
                "--hover-color": THEME["primary"] + "40",
            },
            "nav-link-selected": {
                "background-color": THEME["primary"],
                "color": THEME["text"], "font-weight": "700",
            },
        },
    )

    if selected and selected != active_label:
        target = PAGE_PATHS.get(selected)
        if not target:
            st.error(f"Could not find page file for '{selected}'. Resolved map: {PAGE_PATHS}")
            return selected
        full_path = os.path.join(_PROJECT_ROOT, target.replace("/", os.sep))
        if not os.path.isfile(full_path):
            st.error(f"Page file does not exist on disk: {full_path}")
            return selected
        try:
            st.switch_page(target)
        except Exception as e:
            st.error(f"Navigation error opening '{target}': {e}")

    return selected


def _file_to_base64(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def inject_keyboard_sound():
    click_path = os.path.join(_PROJECT_ROOT, "assets", "keyclick.mp3")
    b64 = _file_to_base64(click_path)
    if not b64:
        return
    st.markdown(
        f"""
        <audio id="keyclick-audio" preload="auto">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mpeg">
        </audio>
        <script>
            (function() {{
                if (window.__keyclick_attached__) return;
                window.__keyclick_attached__ = true;
                document.addEventListener('keydown', function(e) {{
                    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
                    if (tag === 'input' || tag === 'textarea') {{
                        const a = document.getElementById('keyclick-audio');
                        if (a) {{
                            try {{ a.currentTime = 0; a.volume = 0.35; a.play(); }} catch (err) {{}}
                        }}
                    }}
                }});
            }})();
        </script>
        """,
        unsafe_allow_html=True,
    )


def inject_audio_autoplay_helper():
    st.markdown(
        """
        <script>
            (function() {
                if (window.__bg_autoplay_attached__) return;
                window.__bg_autoplay_attached__ = true;
                const tryPlay = function() {
                    const audios = window.parent.document.querySelectorAll('audio');
                    audios.forEach(a => {
                        if (a.id !== 'keyclick-audio') {
                            try { a.volume = 0.25; a.play(); } catch (e) {}
                        }
                    });
                };
                document.addEventListener('click', tryPlay, { once: true });
                document.addEventListener('keydown', tryPlay, { once: true });
            })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def sidebar_audio_player():
    bg_path = os.path.join(_PROJECT_ROOT, "assets", "background.mp3")
    if not os.path.exists(bg_path):
        st.markdown(
            f"<div style='color:{THEME['faint']};font-size:0.8rem;'>Background music file missing</div>",
            unsafe_allow_html=True,
        )
        return
    b64 = _file_to_base64(bg_path)
    st.markdown(
        f"""
        <div style="margin-top:0.4rem;">
            <div style="font-size:0.8rem;color:{THEME['muted']};margin-bottom:0.3rem;">Background Music</div>
            <audio controls loop style="width:100%;">
                <source src="data:audio/mp3;base64,{b64}" type="audio/mpeg">
            </audio>
        </div>
        """,
        unsafe_allow_html=True,
    )