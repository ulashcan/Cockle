import json
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GEMINI_API_KEY")
print(f"Sistem Kontrolü - API Key Yüklendi mi?: {bool(api_key)}")


os.environ["GOOGLE_API_USE_MTLS"] = "never"

from html import escape
from importlib import import_module

from google import genai
import streamlit as st
import plotly.graph_objects as go
import sqlite3

try:
	load_dotenv = import_module("dotenv").load_dotenv
except Exception:
	def load_dotenv() -> bool:
		return False


load_dotenv()


st.set_page_config(page_title="Cockle", page_icon="", layout="wide")


st.markdown(
	"""
	<style>
		@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap');

		:root {
			--bg-primary: #090a0e;
			--bg-secondary: #11141b;
			--line-subtle: #2a2f3c;
			--text-primary: #f3f5f8;
			--text-muted: #a8b0bf;
		}

		html, body, [class*="css"] {
			font-family: 'Space Grotesk', sans-serif;
		}

		.stApp {
			background: radial-gradient(circle at top right, #1a1f2b 0%, var(--bg-primary) 46%);
			color: var(--text-primary);
		}

		header {visibility: hidden;}
		#MainMenu {visibility: hidden;}
		footer {visibility: hidden;}
		.block-container {
			padding-top: 1rem;
			padding-bottom: 0rem;
		}

		[data-testid="stSidebar"] {
			background: linear-gradient(180deg, #0c0d12 0%, #0f1218 100%);
			border-right: 1px solid var(--line-subtle);
		}

		[data-testid="stSidebar"] * {
			color: var(--text-primary);
		}

		h1, h2, h3 {
			color: var(--text-primary) !important;
			letter-spacing: 0.2px;
		}

		.cockle-shell {
			background: rgba(17, 20, 27, 0.9);
			border: 1px solid var(--line-subtle);
			border-radius: 14px;
			padding: 0.95rem 1.05rem;
			margin-top: 0.45rem;
			min-height: 260px;
			box-shadow: 0 12px 32px rgba(0, 0, 0, 0.26);
		}

		.cockle-shell p {
			color: var(--text-muted);
			line-height: 1.55;
			margin: 0;
			white-space: pre-wrap;
		}

		.analysis-box {
			margin-top: 1.2rem;
			background: #11141b;
			border: 1px solid #1f2532;
			border-radius: 6px;
			padding: 1.25rem;
			box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		}

		.analysis-box h4 {
			margin: 0 0 0.45rem 0;
			color: var(--text-primary);
			font-weight: 600;
		}

		.analysis-box p {
			margin: 0;
			color: var(--text-muted);
			line-height: 1.55;
			white-space: pre-wrap;
		}
	</style>
	""",
	unsafe_allow_html=True,
)


def init_db():
	conn = sqlite3.connect("cockle_cache.db")
	c = conn.cursor()
	c.execute('''CREATE TABLE IF NOT EXISTS searches
				 (query TEXT PRIMARY KEY, response_json TEXT)''')
	conn.commit()
	conn.close()

init_db()

def _extract_text(value: object, fallback: str = "") -> str:
	if isinstance(value, str):
		return value.strip()
	if isinstance(value, list):
		parts = [item.strip() for item in value if isinstance(item, str)]
		return "\n".join([item for item in parts if item]).strip() or fallback
	return fallback


def _default_payload(phrase: str, reason: str) -> dict:
	return {
		"en_context": f"Input phrase: {phrase}\n\n{reason}",
		"es_text": "Spanish output unavailable.",
		"it_text": "Italian output unavailable.",
		"contrast_analysis": "Contrast analysis unavailable.",
		"cefr_level": "N/A",
		"cached": False,
		"danger_alert": {"is_risky": False, "warning": "No warning available."},
		"etymology": {"en_path": "N/A", "es_path": "N/A", "it_path": "N/A"},
		"key_differences": [],
		"metrics": {
			"en_es": {"etymology": 0, "grammar": 0, "phonetics": 0},
			"en_it": {"etymology": 0, "grammar": 0, "phonetics": 0},
			"es_it": {"etymology": 0, "grammar": 0, "phonetics": 0},
		},
	}


def extract_json(text: str) -> str:
	start = text.find("{")
	end = text.rfind("}")
	if start == -1 or end == -1 or end <= start:
		return text
	return text[start : end + 1]


def _format_api_error(exc: Exception) -> str:
	error_type = type(exc).__name__
	details = str(exc).strip() or repr(exc)
	parts = [f"{error_type}: {details}"]
	response = getattr(exc, "response", None)
	if response is not None:
		status_code = getattr(response, "status_code", None)
		if status_code is not None:
			parts.append(f"status_code={status_code}")
		text = getattr(response, "text", None)
		if isinstance(text, str) and text.strip():
			parts.append(f"api_response={text.strip()[:600]}")
	return " | ".join(parts)


def _resolve_api_key() -> str:
	secret_key = ""
	try:
		secret_key = (st.secrets.get("GEMINI_API_KEY") or "").strip()
	except Exception:
		secret_key = ""
	if secret_key:
		return secret_key
	return os.getenv("GEMINI_API_KEY", "").strip()


PREFERRED_MODELS = [
	"gemini-2.5-flash",
	"models/gemini-2.5-flash",
	"gemini-flash-latest",
	"models/gemini-flash-latest",
	"gemini-2.0-flash",
	"models/gemini-2.0-flash",
]


def _extract_response_text(response: object) -> str:
	text = getattr(response, "text", None)
	if isinstance(text, str) and text.strip():
		return text

	candidates = getattr(response, "candidates", []) or []
	for candidate in candidates:
		content = getattr(candidate, "content", None)
		parts = getattr(content, "parts", []) or []
		for part in parts:
			part_text = getattr(part, "text", None)
			if isinstance(part_text, str) and part_text.strip():
				return part_text

	if isinstance(response, dict):
		return (
			response.get("candidates", [{}])[0]
			.get("content", {})
			.get("parts", [{}])[0]
			.get("text", "")
		)

	return ""


def _generate_with_sdk(
	api_key: str,
	prompt_text: str,
) -> str:
	client = genai.Client(api_key=api_key)
	last_error = None

	for model in PREFERRED_MODELS:
		try:
			response = client.models.generate_content(
				model=model,
				contents=prompt_text,
			)
			response_text = _extract_response_text(response)
			if response_text.strip():
				return response_text
			last_error = Exception(f"Model {model} returned empty text.")
		except Exception as exc:
			last_error = exc
			continue

	raise Exception(_format_api_error(last_error or Exception("No model call succeeded.")))


@st.cache_data(ttl=600, show_spinner=False)
def build_comparative_content(
	phrase: str,
	api_key: str,
) -> dict:
	if not api_key:
		return _default_payload(phrase, "Configuration missing.")

	try:
		conn = sqlite3.connect("cockle_cache.db")
		c = conn.cursor()
		c.execute("SELECT response_json FROM searches WHERE query=?", (phrase,))
		row = c.fetchone()
		conn.close()
		if row:
			content = json.loads(row[0])
			content["cached"] = True
			return {
				"en_context": _extract_text(content.get("en_context"), "No English context generated."),
				"es_text": _extract_text(content.get("es_text"), "No Spanish text generated."),
				"it_text": _extract_text(content.get("it_text"), "No Italian text generated."),
				"contrast_analysis": _extract_text(content.get("contrast_analysis"), "No contrast analysis generated."),
				"cefr_level": _extract_text(content.get("cefr_level"), "N/A"),
				"cached": content.get("cached", False),
				"danger_alert": content.get("danger_alert", {"is_risky": False, "warning": "No warning available."}),
				"etymology": content.get("etymology", {"en_path": "N/A", "es_path": "N/A", "it_path": "N/A"}),
				"key_differences": content.get("key_differences", []),
				"metrics": content.get("metrics", _default_payload("", "")["metrics"]),
			}
	except Exception as e:
		pass

	prompt = f"""
System Instruction: Your primary role is not just to translate, but to act as a Cognitive Linguistic Expert. Focus 100% on the structural, phonetic, and semantic INTERFERENCE between English, Spanish, and Italian. If a word is a false friend, highlight it aggressively in the danger_alert.

Translate this English phrase to Spanish and Italian. Compare them like a philologist.
Highlight false friends and grammar interference.
English phrase: {phrase}
Include a 'cefr_level' field (e.g., 'A1', 'B2', 'C1') for the input phrase.
For similarity metrics, provide integer percentage scores (0-100) for etymology, grammar, and phonetics.
Also include a 'danger_alert' if there's a false friend or cognitive trap, an 'etymology' tree formatted like a terminal path (e.g. 'PIE -> Latin -> Italian'), and 'key_differences' as a list of 2-3 short strings of quick-fire tips on why ES/IT are different.
Return ONLY a JSON object exactly like this: {{"en_context": "...", "es_text": "...", "it_text": "...", "contrast_analysis": "...", "cefr_level": "...", "danger_alert": {{"is_risky": false, "warning": "..."}}, "etymology": {{"en_path": "...", "es_path": "...", "it_path": "..."}}, "key_differences": ["...", "..."], "metrics": {{"en_es": {{"etymology": 0, "grammar": 0, "phonetics": 0}}, "en_it": {{"etymology": 0, "grammar": 0, "phonetics": 0}}, "es_it": {{"etymology": 0, "grammar": 0, "phonetics": 0}}}}}}
""".strip()

	try:
		response_text = _generate_with_sdk(api_key, prompt)
		content = json.loads(extract_json(response_text))
		try:
			conn = sqlite3.connect("cockle_cache.db")
			c = conn.cursor()
			c.execute("INSERT OR REPLACE INTO searches (query, response_json) VALUES (?, ?)", (phrase, json.dumps(content)))
			conn.commit()
			conn.close()
		except Exception:
			pass
		
		return {
			"en_context": _extract_text(content.get("en_context"), "No English context generated."),
			"es_text": _extract_text(content.get("es_text"), "No Spanish text generated."),
			"it_text": _extract_text(content.get("it_text"), "No Italian text generated."),
			"contrast_analysis": _extract_text(content.get("contrast_analysis"), "No contrast analysis generated."),
			"cefr_level": _extract_text(content.get("cefr_level"), "N/A"),
			"cached": content.get("cached", False),
			"danger_alert": content.get("danger_alert", {"is_risky": False, "warning": "No warning available."}),
			"etymology": content.get("etymology", {"en_path": "N/A", "es_path": "N/A", "it_path": "N/A"}),
			"key_differences": content.get("key_differences", []),
			"metrics": content.get("metrics", _default_payload("", "")["metrics"]),
		}
	except Exception as exc:
		raise exc


st.title("Cockle")

with st.sidebar:
	st.header("Control")
	st.caption("Pure intelligence mode: input-driven comparison")


typed_phrase = st.text_input("Type any word or phrase to compare...", value="")
phrase_to_process = typed_phrase.strip() or "Hello"

api_key = _resolve_api_key()

try:
	with st.spinner("Thinking..."):
		content = build_comparative_content(phrase_to_process, api_key)

	safe_content = {}
	for key, value in content.items():
		if key in ["metrics", "danger_alert", "etymology", "cached", "key_differences"]:
			safe_content[key] = value
		else:
			safe_content[key] = escape(str(value))

	alert = safe_content.get("danger_alert", {})
	if alert.get("is_risky"):
		st.error(f"⚠️ **COGNITIVE TRAP DETECTED:** {escape(str(alert.get('warning', '')))}")

	col1, col2, col3 = st.columns(3)

	with col1:
		st.subheader(f"EN Context `{safe_content.get('cefr_level', 'N/A')}`")
		st.markdown(
			f"""
			<div class="cockle-shell">
				<p>{safe_content['en_context']}</p>
			</div>
			""",
			unsafe_allow_html=True,
		)

	with col2:
		st.subheader("ES")
		st.markdown(
			f"""
			<div class="cockle-shell">
				<p>{safe_content['es_text']}</p>
			</div>
			""",
			unsafe_allow_html=True,
		)

	with col3:
		st.subheader("IT")
		st.markdown(
			f"""
			<div class="cockle-shell">
				<p>{safe_content['it_text']}</p>
			</div>
			""",
			unsafe_allow_html=True,
		)

	st.write("")
	st.subheader("Linguistic Proximity")

	metrics = safe_content.get("metrics", _default_payload("", "")["metrics"])

	pair_options = {"EN / ES": "en_es", "EN / IT": "en_it", "ES / IT": "es_it"}
	selected_label = st.radio("Language Pair", list(pair_options.keys()), horizontal=True, label_visibility="collapsed")
	selected_key = pair_options[selected_label]
	selected_metrics = metrics.get(selected_key, {"etymology": 0, "grammar": 0, "phonetics": 0})

	categories = ['Etymology', 'Grammar', 'Phonetics']
	values = [selected_metrics.get("etymology", 0), selected_metrics.get("grammar", 0), selected_metrics.get("phonetics", 0)]

	fig = go.Figure(data=go.Scatterpolar(
		r=values + [values[0]],
		theta=categories + [categories[0]],
		fill='toself',
		mode='lines+markers+text',
		text=values + [""],
		textposition='top center',
		textfont=dict(color='#f3f5f8', size=12),
		line_color='#8f98a9',
		fillcolor='rgba(143, 152, 169, 0.2)'
	))

	fig.update_layout(
		template='plotly_dark',
		paper_bgcolor='rgba(0,0,0,0)',
		plot_bgcolor='rgba(0,0,0,0)',
		polar=dict(
			radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor='#2a2f3c'),
			angularaxis=dict(gridcolor='#2a2f3c', linecolor='#2a2f3c')
		),
		margin=dict(l=0, r=0, t=20, b=20),
		height=300
	)

	st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

	st.write("")
	st.subheader("Root Tracker")
	ety = safe_content.get("etymology", {"en_path": "N/A", "es_path": "N/A", "it_path": "N/A"})
	st.code(f"EN: {ety.get('en_path', 'N/A')}\nES: {ety.get('es_path', 'N/A')}\nIT: {ety.get('it_path', 'N/A')}", language="bash")

	key_diffs = safe_content.get("key_differences", [])
	if key_diffs:
		st.write("")
		st.info("**Tutor's Tip - Key Differences:**\n\n" + "\n".join([f"- {escape(str(diff))}" for diff in key_diffs]))

	st.markdown(
		f"""
		<div class="analysis-box">
			<h4>⚠️ Contrast &amp; Interference Analysis</h4>
			<p>{safe_content['contrast_analysis']}</p>
		</div>
		""",
		unsafe_allow_html=True,
	)

	if content.get("cached"):
		st.markdown("<p style='text-align: right; color: var(--text-muted); font-size: 0.8rem; margin-top: 1rem;'>⚡ Cached</p>", unsafe_allow_html=True)
except Exception as e:
	st.warning("⚠️ **Analyzing temporarily unavailable.** Please check your input or connection.")