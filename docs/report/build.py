"""Build docs/DeTour_Report.pdf from report.html.

    python3 docs/report/build.py                      # leaves the team fields marked "to be filled in"
    python3 docs/report/build.py --team-id T-042 --team-name "Team Name"

Needs Google Chrome (it prints the page to PDF). The font is bundled in ./fonts.
"""
import argparse
import html
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team-id")
    ap.add_argument("--team-name")
    ap.add_argument("--out", default=str(HERE.parent / "DeTour_Report.pdf"))
    a = ap.parse_args()

    src = (HERE / "report.html").read_text(encoding="utf-8")
    for ident, value in (("team-id", a.team_id), ("team-name", a.team_name)):
        marker = f'<span class="blank" id="{ident}">to be filled in</span>'
        if marker not in src:
            sys.exit(f"report.html is missing the {ident} field")
        if value:
            src = src.replace(marker, f"<b>{html.escape(value)}</b>")

    chrome = next((c for c in CHROME if c and Path(c).exists()), None)
    if not chrome:
        sys.exit("Google Chrome was not found. Install it, or open report.html in a browser and print to PDF.")

    page = HERE / ".report.build.html"  # next to report.html so the font path resolves
    page.write_text(src, encoding="utf-8")
    out = Path(a.out)
    out.unlink(missing_ok=True)
    try:
        with tempfile.TemporaryDirectory() as profile:
            proc = subprocess.Popen(
                [chrome, "--headless=new", "--disable-gpu", f"--user-data-dir={profile}", "--no-pdf-header-footer",
                 f"--print-to-pdf={out}", page.as_uri()],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            try:
                # Chrome writes the file and may not exit by itself: wait until the file stops growing, then stop it
                last, stable, waited = -1, 0, 0.0
                while waited < 90 and stable < 4:
                    time.sleep(0.5)
                    waited += 0.5
                    size = out.stat().st_size if out.exists() else -1
                    stable = stable + 1 if size > 0 and size == last else 0
                    last = size
            finally:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
    finally:
        page.unlink(missing_ok=True)
    if not out.exists() or out.stat().st_size == 0:
        sys.exit("Chrome did not produce a PDF.")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
