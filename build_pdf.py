from fpdf import FPDF
from pathlib import Path

files = [
    "app.py", "home_page.py", "theme.py",
    "pages/1_screener.py",
    "pages/2_auto_valuation.py",
    "pages/3_manual_valuation.py",
    "utils/fx.py",
    "utils/screener_logic.py",
    "utils/valuation_logic.py",
    "utils/ai_helper.py",
    "requirements.txt",
]

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=12)
pdf.add_page()
pdf.set_font("Courier", size=8)

for f in files:
    p = Path(f)
    if not p.exists():
        continue
    pdf.add_page()
    pdf.set_font("Courier", style="B", size=11)
    pdf.cell(0, 8, txt=f"=== {f} ===", ln=True)
    pdf.set_font("Courier", size=7)
    text = p.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        # fpdf can't handle some unicode; strip
        safe = line.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 3, txt=safe)

pdf.output("valuation_tool_source.pdf")
print("Wrote valuation_tool_source.pdf")
