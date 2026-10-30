"""One-off renderer for docs/PROJECT_ARCHITECTURE.pdf. Not used at runtime."""

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path(__file__).with_name("PROJECT_ARCHITECTURE.pdf")

TEAL = HexColor("#0f766e")
NAVY = HexColor("#0f172a")
SLATE = HexColor("#475569")
LINE = HexColor("#94a3b8")
CARD = HexColor("#f8fafc")
OK = HexColor("#047857")
WARN = HexColor("#b45309")
DANGER = HexColor("#b91c1c")
BG = HexColor("#ffffff")


def rounded_box(c, x, y, w, h, title, body, fill=CARD, title_color=NAVY):
    c.setFillColor(fill)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
    c.setFillColor(title_color)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 8, y + h - 14, title)
    c.setFillColor(SLATE)
    c.setFont("Helvetica", 8)
    for i, line in enumerate(body.split("\n")):
        c.drawString(x + 8, y + h - 28 - i * 11, line)


def draw_arrow(c, x1, y1, x2, y2):
    c.setStrokeColor(TEAL)
    c.setFillColor(TEAL)
    c.setLineWidth(1.3)
    c.line(x1, y1, x2, y2)
    size = 6
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    path = c.beginPath()
    path.moveTo(x2, y2)
    path.lineTo(x2 - ux * size + px * size * 0.45, y2 - uy * size + py * size * 0.45)
    path.lineTo(x2 - ux * size - px * size * 0.45, y2 - uy * size - py * size * 0.45)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def header(c, title, subtitle):
    c.setFillColor(TEAL)
    c.rect(0, 277 * mm, 210 * mm, 20 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(16 * mm, 288 * mm, title)
    c.setFont("Helvetica", 9)
    c.drawString(16 * mm, 281 * mm, subtitle)


def footer(c, page, total):
    c.setFillColor(SLATE)
    c.setFont("Helvetica", 8)
    c.drawString(16 * mm, 10 * mm, "Atlas / Multi-Agent RAG Debugger  ·  local architecture, not a live SaaS claim")
    c.drawRightString(194 * mm, 10 * mm, f"{page} / {total}")


def page_architecture(c):
    header(c, "Atlas project architecture", "How the UI, three agents, and demo repos connect")
    # You
    rounded_box(c, 16 * mm, 240 * mm, 50 * mm, 28 * mm, "You", "Browser at localhost:5173\nPaste bug + pick demo repo")
    # Frontend
    rounded_box(c, 80 * mm, 240 * mm, 52 * mm, 28 * mm, "Frontend (Vite)", "New session form\nInbox, diff, Approve")
    # API
    rounded_box(c, 146 * mm, 240 * mm, 48 * mm, 28 * mm, "FastAPI :8000", "/api/v1/repair\nRepairOrchestrator")
    draw_arrow(c, 66 * mm, 254 * mm, 80 * mm, 254 * mm)
    draw_arrow(c, 132 * mm, 254 * mm, 146 * mm, 254 * mm)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(16 * mm, 226 * mm, "Three specialist agents  (no fourth agent)")

    rounded_box(c, 16 * mm, 178 * mm, 56 * mm, 42 * mm, "1. Investigator", "Indexes the chosen folder\nSearches functions/files\nStops if code is missing")
    rounded_box(c, 77 * mm, 178 * mm, 56 * mm, 42 * mm, "2. Repair Engineer", "Writes a unified diff only\nDoes not edit the original\nPatch has a revision hash")
    rounded_box(c, 138 * mm, 178 * mm, 56 * mm, 42 * mm, "3. QA", "Applies patch on a copy\nRuns pytest / node tests\nReports pass or fail")
    draw_arrow(c, 72 * mm, 199 * mm, 77 * mm, 199 * mm)
    draw_arrow(c, 133 * mm, 199 * mm, 138 * mm, 199 * mm)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(16 * mm, 164 * mm, "Data on disk")

    rounded_box(c, 16 * mm, 118 * mm, 58 * mm, 40 * mm, "data/demos  (6 fixtures)", "01 import error\n02 FastAPI 500\n03 JS await\n04 SQLite column\n05 APP_TOKEN\n06 discount regression")
    rounded_box(c, 80 * mm, 128 * mm, 54 * mm, 30 * mm, "SQLite", "data/debugger.db\nsessions, events, patches")
    rounded_box(c, 140 * mm, 128 * mm, 54 * mm, 30 * mm, "Isolated candidate", "Temp copy for tests\nOriginal demo stays broken\nuntil Integrate")

    draw_arrow(c, 44 * mm, 178 * mm, 44 * mm, 158 * mm)
    draw_arrow(c, 166 * mm, 178 * mm, 166 * mm, 158 * mm)

    c.setFillColor(SLATE)
    c.setFont("Helvetica", 8.5)
    notes = [
        "LLM: mock (offline) or openai / openrouter / ollama with real keys. Mock is not a silent fallback for a failed live provider.",
        "Embeddings for local demo runs: hash (no large model). Original demo files are not rewritten until you authorize integration.",
        "GitHub clone by URL is supported. There is no GitHub OAuth and no automatic push to production.",
    ]
    y = 108 * mm
    for note in notes:
        c.drawString(16 * mm, y, "•  " + note)
        y -= 12

    footer(c, 1, 2)


def page_flow(c):
    header(c, "Repair workflow", "What happens after you paste a demo bug in the UI")

    steps = [
        (16, 230, "1. Intake", "Title, description,\nrepo from dropdown"),
        (72, 230, "2. Investigate", "Search real source\nfiles in the demo"),
        (128, 230, "3. Propose", "Unified diff +\nrevision hash"),
        (16, 168, "4. You review", "Approve / reject /\nrequest changes"),
        (72, 168, "5. Test copy", "git apply + pytest\non isolated folder"),
        (128, 168, "6. Finish", "Ready to integrate\nor blocked"),
    ]
    for x, y, title, body in steps:
        rounded_box(c, x * mm, y * mm, 50 * mm, 36 * mm, title, body)

    draw_arrow(c, 66 * mm, 248 * mm, 72 * mm, 248 * mm)
    draw_arrow(c, 122 * mm, 248 * mm, 128 * mm, 248 * mm)
    draw_arrow(c, 153 * mm, 230 * mm, 153 * mm, 210 * mm)
    draw_arrow(c, 128 * mm, 186 * mm, 122 * mm, 186 * mm)
    draw_arrow(c, 72 * mm, 186 * mm, 66 * mm, 186 * mm)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(16 * mm, 150 * mm, "Decision outcomes")

    rounded_box(c, 16 * mm, 108 * mm, 55 * mm, 34 * mm, "Code missing", "BLOCKED\nDefect target not found.\nNo code modifications possible.", title_color=DANGER)
    rounded_box(c, 77 * mm, 108 * mm, 55 * mm, 34 * mm, "Tests fail 3 times", "BLOCKED\nRepair iteration limit.\nStart a New session.", title_color=WARN)
    rounded_box(c, 138 * mm, 108 * mm, 56 * mm, 34 * mm, "Tests pass", "READY_FOR_INTEGRATION\nOriginal project unchanged\nuntil you authorize copy-in.", title_color=OK)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(16 * mm, 94 * mm, "How to use a demo")

    c.setFillColor(SLATE)
    c.setFont("Helvetica", 9)
    lines = [
        "1. API:  python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000",
        "2. UI:   cd frontend   then   npm run dev    →  http://localhost:5173",
        "3. New session. Pick a data/demos folder. Paste title/description from that demo's BUG_REPORT.md.",
        "4. Investigate. Read the diff. Approve only that patch revision.",
        "5. If the session is already BLOCKED, do not retry it — open New session.",
        "Demo 1 expected patch:  from greeter import greet  →  from greeting import greet",
    ]
    y = 80 * mm
    for line in lines:
        c.drawString(16 * mm, y, line)
        y -= 11

    footer(c, 2, 2)


def main() -> None:
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle("Atlas project architecture")
    c.setAuthor("Multi-Agent RAG Debugger")
    page_architecture(c)
    c.showPage()
    page_flow(c)
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
