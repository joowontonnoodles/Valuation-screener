import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

try:
    from pdf2image import convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# ── SocGen CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #0a0a0a; color: #f0f0f0; }
.stApp { background-color: #0a0a0a; }
h1 { color: #E60028; font-weight: 600; font-size: 1.35rem; letter-spacing: 0.04em;
     border-bottom: 2px solid #E60028; padding-bottom: 8px; margin-bottom: 4px; }
h2, h3 { color: #f0f0f0; font-weight: 500; font-size: 0.82rem; letter-spacing: 0.1em;
          text-transform: uppercase; margin-top: 28px; margin-bottom: 6px; }
.header-bar { display: flex; justify-content: space-between; align-items: baseline;
    border-bottom: 1px solid #2a2a2a; padding-bottom: 6px; margin-bottom: 20px; }
.bank-name { color: #E60028; font-size: 1.05rem; font-weight: 600; letter-spacing: 0.05em; }
.header-meta { color: #666; font-size: 0.75rem; }
.ratio-row { display: flex; gap: 18px; margin: 12px 0 24px 0; }
.ratio-card { flex: 1; background: #111; border: 1px solid #1e1e1e; border-left: 3px solid #E60028; padding: 14px 18px; }
.ratio-label { color: #666; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 8px; }
.ratio-vals { display: flex; gap: 18px; align-items: baseline; flex-wrap: wrap; }
.ratio-curr { color: #f0f0f0; font-size: 1.25rem; font-weight: 500; }
.ratio-prior { color: #444; font-size: 0.85rem; }
.chg-pos { color: #4caf50; font-size: 0.8rem; }
.chg-neg { color: #E60028; font-size: 0.8rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.8rem; margin: 8px 0 18px 0; }
th { background: #111; color: #555; font-weight: 500; text-transform: uppercase;
     letter-spacing: 0.07em; font-size: 0.67rem; padding: 7px 10px; border-bottom: 1px solid #222; text-align: right; }
th:first-child { text-align: left; }
td { padding: 6px 10px; border-bottom: 1px solid #161616; color: #bbb; text-align: right; }
td:first-child { text-align: left; color: #e0e0e0; }
tr:hover td { background: #0e0e0e; }
.pos { color: #4caf50; } .neg { color: #E60028; }
.conc-item { display: flex; align-items: baseline; gap: 10px; padding: 5px 0; border-bottom: 1px solid #161616; }
.conc-rank { color: #E60028; font-size: 0.7rem; font-weight: 600; min-width: 18px; }
.conc-name { color: #ccc; font-size: 0.8rem; flex: 1; }
.conc-pct { color: #f0f0f0; font-size: 0.8rem; font-weight: 500; min-width: 55px; text-align: right; }
.conc-val { color: #555; font-size: 0.74rem; min-width: 130px; text-align: right; }
.unit-badge { background: #1a1a1a; border: 1px solid #2a2a2a; color: #888;
              font-size: 0.68rem; padding: 2px 8px; border-radius: 2px; display: inline-block; margin-bottom: 14px; }
hr { border-color: #1a1a1a; margin: 22px 0; }
[data-testid="stFileUploader"] { border: 1px solid #1e1e1e; background: #0e0e0e; padding: 4px; }
[data-testid="stDownloadButton"] > button { background: transparent; border: 1px solid #E60028;
    color: #E60028; font-size: 0.72rem; padding: 5px 14px; letter-spacing: 0.05em; text-transform: uppercase; }
[data-testid="stDownloadButton"] > button:hover { background: #E60028; color: #fff; }
[data-testid="stExpander"] { border: 1px solid #1e1e1e !important; background: #0a0a0a; }
summary { color: #444 !important; font-size: 0.72rem !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def to_num(s):
    if not isinstance(s, str): return None
    s = s.strip().replace(",", "").replace("\xa0", "").replace(" ", "")
    s = re.sub(r"HK\$|US\$|'000|港幣千元|%|—|–|-{2,}", "", s)
    s = s.strip()
    if s in ("", "—", "-", "Nil", "nil"): return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[()$]", "", s)
    try:
        v = float(s)
        return -v if neg else v
    except:
        return None

def nums_from_line(line):
    tokens = re.findall(r"\([\d,]+(?:\.\d+)?\)|[\d,]+(?:\.\d+)?", line)
    return [v for t in tokens for v in [to_num(t)] if v is not None]

def detect_unit(text):
    """Return multiplier: 1 for '000s, 1000 for millions (to normalise to HKD units)."""
    text_lower = text.lower()
    if re.search(r"in millions|million[s]? of hk|hkd.*million|million.*hkd|millions of hong kong", text_lower):
        return 1_000_000, "HKD millions"
    if re.search(r"'000|thousands|in thousands|hkd.*'000", text_lower):
        return 1_000, "HKD thousands"
    # Default assumption: thousands (most HKMA docs)
    return 1_000, "HKD thousands (assumed)"

def extract_pages(pdf_bytes):
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            rows = []
            for tbl in (page.extract_tables() or []):
                for row in tbl:
                    rows.append([c.strip() if isinstance(c, str) else (c or "") for c in row])
            pages.append((i, lines, rows))
    return pages

def ocr_text(pdf_bytes):
    if not OCR_AVAILABLE: return ""
    imgs = convert_from_bytes(pdf_bytes, dpi=200)
    return "\n".join(pytesseract.image_to_string(img) for img in imgs)

# ─────────────────────────────────────────────────────────────────────────────
# BALANCE SHEET PARSER — reads assets and liabilities in order from the page
# This replaces the hardcoded pattern lists and fixes ordering/amount bugs.
# ─────────────────────────────────────────────────────────────────────────────

# Lines to skip (totals, headers, section dividers)
SKIP_PATTERNS = [
    r"^total\s+assets", r"^total\s+liabilities", r"^assets$", r"^liabilities$",
    r"^section", r"^ii\.", r"^i\.", r"balance sheet", r"^\d+$",
    r"jpmorgan|credit agricole|bnp paribas|hong kong branch",
    r"as at|as of|dec\s+\d|jun\s+\d",
    r"hk\$|in millions|in thousands|港幣",
    r"^page\s*\d", r"^\d+\s*$",
    r"less:\s*impairment",   # subtraction rows distort concentrations
    r"provision|impairment allowance",
]

def should_skip(label):
    ll = label.lower().strip()
    for pat in SKIP_PATTERNS:
        if re.search(pat, ll, re.IGNORECASE):
            return True
    return False

def parse_balance_sheet_section(lines, rows, section="assets"):
    """
    Parse either the Assets or Liabilities section of the balance sheet.
    Returns list of {label, curr, prior} dicts, in document order.
    Strategy: use pdfplumber table rows first (more reliable); fall back to text lines.
    """
    items = []

    # ── Try table rows first ──────────────────────────────────────────────────
    in_section = False
    end_trigger = r"total\s+liabilities|total\s+assets" if section == "assets" else r"end_never_match"
    start_trigger = r"^assets$|assets\s*$" if section == "assets" else r"^liabilities$|liabilities\s*$"

    for row in rows:
        cells = [c.strip() for c in row if isinstance(c, str) and c.strip()]
        if not cells: continue
        label = cells[0]
        ll = label.lower()

        if re.search(start_trigger, ll, re.IGNORECASE):
            in_section = True; continue
        if in_section and re.search(r"total\s+(assets|liabilities)", ll, re.IGNORECASE):
            if section == "assets" and "liabilities" not in ll: in_section = False; continue
            elif section == "liabilities": in_section = False; continue
        if not in_section: continue
        if should_skip(label): continue

        nums = [to_num(c) for c in cells[1:] if to_num(c) is not None]
        if len(nums) >= 2:
            items.append({"label": label, "curr": nums[0], "prior": nums[1]})
        elif len(nums) == 1:
            items.append({"label": label, "curr": nums[0], "prior": None})

    if items:
        return items

    # ── Fallback: text line scanning ──────────────────────────────────────────
    in_section = False
    for i, line in enumerate(lines):
        ll = line.lower()
        if re.search(start_trigger, ll, re.IGNORECASE):
            in_section = True; continue
        if in_section and re.search(r"total\s+(assets|liabilities)", ll, re.IGNORECASE):
            in_section = False; continue
        if not in_section: continue
        if should_skip(line): continue

        nums = nums_from_line(line)
        # strip the label (non-numeric prefix)
        label_match = re.match(r"^([^\d\(]+)", line)
        label = label_match.group(1).strip() if label_match else line
        if label and len(nums) >= 1:
            items.append({
                "label": label,
                "curr": nums[0],
                "prior": nums[1] if len(nums) >= 2 else None,
            })

    return items

# ─────────────────────────────────────────────────────────────────────────────
# TARGETED METRIC FINDERS
# ─────────────────────────────────────────────────────────────────────────────
def find_val(lines, rows, pattern):
    for row in rows:
        joined = " ".join(str(c) for c in row).lower()
        if re.search(pattern, joined):
            nums = [to_num(c) for c in row if to_num(c) is not None]
            if len(nums) >= 2: return nums[0], nums[1]
    for i, line in enumerate(lines):
        if re.search(pattern, line, re.IGNORECASE):
            nums = nums_from_line(line)
            if len(nums) >= 2: return nums[0], nums[1]
            for j in range(i + 1, min(i + 4, len(lines))):
                nums += nums_from_line(lines[j])
                if len(nums) >= 2: return nums[0], nums[1]
    return None

def get_provisions(lines, rows):
    """
    Handles both layouts:
    - CA-CIB: 'Impairment allowances for loans and advances' block with Collective / Specific sub-rows
    - JPM: 'Collective provisions' / 'Specific provisions' as standalone rows in loans section
    Returns dict with spec/coll values or None.
    """
    spec, coll = None, None

    # Layout 1: standalone labelled rows (JPM style)
    for row in rows:
        cells = [c.strip() for c in row if isinstance(c, str)]
        label = cells[0].lower() if cells else ""
        nums  = [to_num(c) for c in cells[1:] if to_num(c) is not None]
        if re.search(r"specific\s+provision|specific\s+impairment", label) and len(nums) >= 2:
            spec = (abs(nums[0]), abs(nums[1]))
        if re.search(r"collective\s+provision|collective\s+impairment", label) and len(nums) >= 2:
            coll = (abs(nums[0]), abs(nums[1]))

    # Also scan text lines for standalone labels
    for i, line in enumerate(lines):
        ll = line.lower()
        nums = nums_from_line(line)
        if re.search(r"- collective provisions|collective provisions", ll) and len(nums) >= 2 and coll is None:
            coll = (abs(nums[0]), abs(nums[1]))
        if re.search(r"- specific provisions|specific provisions", ll) and len(nums) >= 2 and spec is None:
            spec = (abs(nums[0]), abs(nums[1]))

    # Layout 2: CA-CIB block style (impairment allowances for loans and advances)
    if spec is None and coll is None:
        in_loans = False
        for line in lines:
            ll = line.lower()
            if re.search(r"impairment allowances for loans and advances", ll):
                in_loans = True; continue
            if re.search(r"impairment allowances for other claims", ll):
                in_loans = False; continue
            if in_loans:
                nums = nums_from_line(line)
                if len(nums) >= 2:
                    if re.search(r"collective|組合", ll) and coll is None:
                        coll = (abs(nums[0]), abs(nums[1]))
                    elif re.search(r"specific|特定", ll) and spec is None:
                        spec = (abs(nums[0]), abs(nums[1]))

    return {"spec": spec, "coll": coll}

def get_lmr_cfr(lines, pdf_bytes):
    lmr = find_val(lines, [], r"average\s+(liquidity maintenance|lmr)")
    cfr = find_val(lines, [], r"average\s+(core funding|cfr)")
    if not (lmr and cfr):
        raw  = ocr_text(pdf_bytes)
        ol   = [l.strip() for l in raw.splitlines() if l.strip()]
        if not lmr: lmr = find_val(ol, [], r"average.*lmr|lmr.*%")
        if not cfr: cfr = find_val(ol, [], r"average.*cfr|cfr.*%")
    return lmr, cfr

def get_total(lines, rows, pattern):
    return find_val(lines, rows, pattern)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
def run(pdf_bytes):
    pages = extract_pages(pdf_bytes)
    all_lines, all_rows = [], []
    for _, lines, rows in pages:
        all_lines += lines
        all_rows  += rows

    full_text = "\n".join(all_lines)
    unit_mult, unit_label = detect_unit(full_text)

    d = {}
    d["unit_mult"]  = unit_mult
    d["unit_label"] = unit_label

    d["ta"]     = get_total(all_lines, all_rows, r"total\s+assets|總資產")
    d["tl"]     = get_total(all_lines, all_rows, r"total\s+liabilities|總負債")
    d["profit"] = find_val(all_lines, all_rows, r"profit after tax|餘稅後盈利")
    prov        = get_provisions(all_lines, all_rows)
    d["spec"]   = prov["spec"]
    d["coll"]   = prov["coll"]
    d["lmr"], d["cfr"] = get_lmr_cfr(all_lines, pdf_bytes)

    # Balance sheet items — read directly in document order
    d["asset_items"] = parse_balance_sheet_section(all_lines, all_rows, "assets")
    d["liab_items"]  = parse_balance_sheet_section(all_lines, all_rows, "liabilities")

    return d

# ─────────────────────────────────────────────────────────────────────────────
# FORMATTING
# ─────────────────────────────────────────────────────────────────────────────
def fmt_n(v, unit_mult):
    if v is None: return "—"
    # Display in original document units
    return f"{abs(v):,.0f}"

def pct_chg(c, p):
    if c is None or p is None or p == 0: return None
    return round((c - p) / abs(p) * 100, 2)

def fmt_chg(v, suffix="%"):
    if v is None: return "—"
    sign = "+" if v > 0 else ""
    css  = "pos" if v > 0 else "neg"
    return f'<span class="{css}">{sign}{v:.2f}{suffix}</span>'

def pp_span(v):
    if v is None: return "—"
    sign = "+" if v > 0 else ""
    css  = "chg-pos" if v > 0 else "chg-neg"
    return f'<span class="{css}">{sign}{v:.2f}pp</span>'

# ─────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("<h1>HKMA DISCLOSURE READER</h1>", unsafe_allow_html=True)
uploaded = st.file_uploader("Upload HKMA Key Financial Information Disclosure Statement (PDF)", type="pdf")

if uploaded:
    pdf_bytes = uploaded.read()
    with st.spinner(""):
        d = run(pdf_bytes)

    um   = d["unit_mult"]
    ul   = d["unit_label"]
    ta   = d["ta"]
    tl   = d["tl"]
    spec = d["spec"]
    coll = d["coll"]
    lmr  = d["lmr"]
    cfr  = d["cfr"]
    prof = d["profit"]
    ai   = d["asset_items"]
    li   = d["liab_items"]

    tot_prov = None
    if spec and coll:
        tot_prov = (spec[0] + coll[0], spec[1] + coll[1])
    elif coll:
        tot_prov = coll
    elif spec:
        tot_prov = spec

    bank = uploaded.name.replace(".pdf", "").replace("_", " ").upper()

    # ── Header ──────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="header-bar">
      <span class="bank-name">{bank}</span>
      <span class="header-meta">Source: HKMA &nbsp;|&nbsp; {ul}</span>
    </div>
    <div class="unit-badge">{ul}</div>
    """, unsafe_allow_html=True)

    # ── Liquidity ratios ─────────────────────────────────────────────────────
    st.markdown("<h3>Liquidity Ratios — Q4 YoY</h3>", unsafe_allow_html=True)
    lmr_pp = round(lmr[0] - lmr[1], 2) if lmr else None
    cfr_pp = round(cfr[0] - cfr[1], 2) if cfr else None

    st.markdown(f"""
    <div class="ratio-row">
      <div class="ratio-card">
        <div class="ratio-label">3m Liquidity Maintenance Ratio (LMR)</div>
        <div class="ratio-vals">
          <span class="ratio-curr">{f"{lmr[0]:.2f}%" if lmr else "—"}</span>
          <span class="ratio-prior">{f"{lmr[1]:.2f}% prior" if lmr else ""}</span>
          {pp_span(lmr_pp)}
        </div>
      </div>
      <div class="ratio-card">
        <div class="ratio-label">3m Core Funding Ratio (CFR)</div>
        <div class="ratio-vals">
          <span class="ratio-curr">{f"{cfr[0]:.2f}%" if cfr else "—"}</span>
          <span class="ratio-prior">{f"{cfr[1]:.2f}% prior" if cfr else ""}</span>
          {pp_span(cfr_pp)}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Key financials table ─────────────────────────────────────────────────
    st.markdown("<h3>Key Financials — Half-Year</h3>", unsafe_allow_html=True)

    kf_rows = [
        ("Profit after taxation",    prof),
        ("Total assets",             ta),
        ("Total liabilities",        tl),
        ("Specific provisions",      spec),
        ("Collective provisions",    coll),
        ("Total provisions",         tot_prov),
    ]
    rows_html = ""
    for label, pair in kf_rows:
        if pair:
            c, p = pair[0], pair[1]
            rows_html += f"<tr><td>{label}</td><td>{fmt_n(c,um)}</td><td>{fmt_n(p,um)}</td><td>{fmt_chg(pct_chg(c,p))}</td></tr>"
        else:
            rows_html += f"<tr><td>{label}</td><td>—</td><td>—</td><td>—</td></tr>"

    st.markdown(f"""
    <table>
      <thead><tr><th>Item</th><th>Current</th><th>Prior</th><th>Change</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    """, unsafe_allow_html=True)

    # ── Asset concentration top 3 ────────────────────────────────────────────
    def conc_section(items, total_val, section_title):
        if not items or not total_val: return
        valid = [x for x in items if x["curr"] is not None and abs(x["curr"]) > 0]
        valid.sort(key=lambda x: abs(x["curr"]), reverse=True)
        top3 = valid[:3]
        st.markdown(f"<h3>{section_title} — Top 3</h3>", unsafe_allow_html=True)
        html = '<div>'
        for i, x in enumerate(top3, 1):
            pct = round(abs(x["curr"]) / abs(total_val[0]) * 100, 2) if total_val[0] else 0
            html += f"""<div class="conc-item">
              <span class="conc-rank">#{i}</span>
              <span class="conc-name">{x['label']}</span>
              <span class="conc-pct">{pct:.2f}%</span>
              <span class="conc-val">{ul.split()[0]} {fmt_n(x['curr'],um)}</span>
            </div>"""
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    conc_section(ai, ta, "Asset Concentration")
    conc_section(li, tl, "Liability Concentration")

    # ── Full asset breakdown ─────────────────────────────────────────────────
    def full_breakdown(items, total_val, title):
        if not items or not total_val: return
        valid = [x for x in items if x["curr"] is not None]
        valid.sort(key=lambda x: abs(x["curr"]) if x["curr"] else 0, reverse=True)
        st.markdown(f"<h3>{title}</h3>", unsafe_allow_html=True)
        rows_h = ""
        for x in valid:
            pct_c = round(abs(x["curr"]) / abs(total_val[0]) * 100, 2) if total_val[0] and x["curr"] else None
            pct_p = round(abs(x["prior"]) / abs(total_val[1]) * 100, 2) if total_val[1] and x.get("prior") else None
            rows_h += f"""<tr>
              <td>{x['label']}</td>
              <td>{fmt_n(x['curr'],um)}</td>
              <td>{"—" if pct_c is None else f"{pct_c:.2f}%"}</td>
              <td>{fmt_n(x.get('prior'),um)}</td>
              <td>{"—" if pct_p is None else f"{pct_p:.2f}%"}</td>
            </tr>"""
        st.markdown(f"""
        <table>
          <thead><tr>
            <th>Item</th>
            <th>Current</th><th>% of Total</th>
            <th>Prior</th><th>% of Total</th>
          </tr></thead>
          <tbody>{rows_h}</tbody>
        </table>
        """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    full_breakdown(ai, ta, "Full Asset Breakdown")
    full_breakdown(li, tl, "Full Liability Breakdown")

    # ── CSV download ─────────────────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    export = []
    for label, pair in kf_rows:
        if pair:
            export.append({"Section":"Key Financials","Item":label,
                           "Current":pair[0],"Prior":pair[1],"Change%":pct_chg(pair[0],pair[1])})
    if lmr:
        export.append({"Section":"Liquidity","Item":"Average LMR","Current":f"{lmr[0]}%","Prior":f"{lmr[1]}%","Change pp":lmr_pp})
    if cfr:
        export.append({"Section":"Liquidity","Item":"Average CFR","Current":f"{cfr[0]}%","Prior":f"{cfr[1]}%","Change pp":cfr_pp})
    for x in sorted(ai, key=lambda x: abs(x["curr"]) if x["curr"] else 0, reverse=True):
        pct = round(abs(x["curr"]) / abs(ta[0]) * 100, 2) if ta and x["curr"] else None
        export.append({"Section":"Assets","Item":x["label"],"Current":x["curr"],"Prior":x.get("prior"),"% of Total":pct})
    for x in sorted(li, key=lambda x: abs(x["curr"]) if x["curr"] else 0, reverse=True):
        pct = round(abs(x["curr"]) / abs(tl[0]) * 100, 2) if tl and x["curr"] else None
        export.append({"Section":"Liabilities","Item":x["label"],"Current":x["curr"],"Prior":x.get("prior"),"% of Total":pct})

    csv = pd.DataFrame(export).to_csv(index=False).encode("utf-8")
    st.download_button("DOWNLOAD CSV", data=csv,
                       file_name=f"{uploaded.name.replace('.pdf','')}_metrics.csv", mime="text/csv")

    with st.expander("raw extracted lines"):
        pages2 = extract_pages(pdf_bytes)
        dbg = []
        for _,ll,_ in pages2: dbg += ll
        st.text("\n".join(dbg[:300]))
