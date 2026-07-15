"""Zepto brand theme shared by the local HTML Doc and collection dashboard.

Palette mirrors Zepto's public identity: Zepto Purple + Zepto Dark, with soft lavender
surfaces like the consumer website / app shell.
"""

from __future__ import annotations

# Official-ish brand tokens (see zeptonow.com / Zepto purple dominance)
ZEPTO_PURPLE = "#8B5CF6"
ZEPTO_PURPLE_DEEP = "#7C3AED"
ZEPTO_DARK = "#1A1A2E"
ZEPTO_LAVENDER = "#F3EEFF"
ZEPTO_MIST = "#EDE9FE"
ZEPTO_WHITE = "#FFFFFF"
ZEPTO_MUTED = "#6B6580"

FONT_LINK = (
    "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,400;0,500;"
    "0,600;0,700;0,800;1,400&display=swap"
)

DOC_CSS = f"""
  :root {{
    --ink: {ZEPTO_DARK};
    --muted: {ZEPTO_MUTED};
    --line: rgba(139, 92, 246, 0.18);
    --bg: {ZEPTO_LAVENDER};
    --card: {ZEPTO_WHITE};
    --accent: {ZEPTO_PURPLE};
    --accent-deep: {ZEPTO_PURPLE_DEEP};
  }}
  body {{
    font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
    max-width: 880px; margin: 0 auto; padding: 32px 20px 64px;
    color: var(--ink); line-height: 1.55; background:
      radial-gradient(ellipse 70% 50% at 0% -10%, rgba(139, 92, 246, 0.28), transparent 55%),
      radial-gradient(ellipse 50% 40% at 100% 0%, rgba(236, 72, 153, 0.12), transparent 50%),
      linear-gradient(180deg, {ZEPTO_MIST} 0%, {ZEPTO_LAVENDER} 45%, #faf8ff 100%);
  }}
  .banner {{
    background: linear-gradient(135deg, {ZEPTO_DARK} 0%, #2a1848 55%, {ZEPTO_PURPLE_DEEP} 100%);
    border: 0; border-radius: 20px;
    padding: 24px 26px; margin-bottom: 28px; color: #fff;
    box-shadow: 0 12px 32px rgba(26, 26, 46, 0.18);
  }}
  .banner .eyebrow {{
    text-transform: uppercase; letter-spacing: 0.14em; font-size: 11px;
    color: #d8b4fe; font-weight: 700; margin: 0 0 8px;
  }}
  .banner h1 {{ margin: 0; border: 0; padding: 0; font-size: 1.65rem; font-weight: 800;
               letter-spacing: -0.03em; color: #fff; }}
  .banner p {{ margin: 10px 0 0; color: rgba(255,255,255,0.78); }}
  section {{
    background: var(--card); border: 1px solid var(--line); border-radius: 16px;
    padding: 8px 22px 22px; margin-bottom: 20px;
    box-shadow: 0 4px 18px rgba(139, 92, 246, 0.06);
  }}
  h1 {{ border-bottom: 1px solid var(--line); padding-bottom: 8px; margin-top: 28px;
       font-size: 1.25rem; color: var(--ink); font-weight: 800; }}
  h2 {{ margin-top: 22px; color: var(--accent-deep); font-size: 1.05rem; font-weight: 700; }}
  li em {{ color: #3f3a55; }}
  ul {{ padding-left: 1.2rem; }}
  a {{ color: var(--accent-deep); }}
"""


DASHBOARD_CSS = f"""
  :root {{
    --ink: {ZEPTO_DARK};
    --muted: {ZEPTO_MUTED};
    --line: rgba(139, 92, 246, 0.2);
    --panel: rgba(255, 255, 255, 0.88);
    --accent: {ZEPTO_PURPLE};
    --accent-deep: {ZEPTO_PURPLE_DEEP};
    --glow: #c4b5fd;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; min-height: 100vh; color: var(--ink);
    font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
    background:
      radial-gradient(ellipse 70% 55% at 0% 0%, rgba(139, 92, 246, 0.35), transparent 55%),
      radial-gradient(ellipse 55% 45% at 100% 8%, rgba(236, 72, 153, 0.16), transparent 50%),
      linear-gradient(160deg, {ZEPTO_MIST} 0%, {ZEPTO_LAVENDER} 42%, #faf8ff 100%);
  }}
  .wrap {{
    max-width: 1040px; margin: 0 auto; padding: 40px 22px 72px;
  }}
  .brand {{
    font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
    font-size: clamp(2.6rem, 6vw, 3.8rem);
    font-weight: 800; letter-spacing: -0.045em;
    margin: 0; line-height: 1.02; color: var(--ink);
  }}
  .brand span {{ color: var(--accent); }}
  .lede {{
    margin: 10px 0 0; max-width: 36rem; color: var(--muted); font-size: 1.05rem;
  }}
  .hero {{
    display: grid; gap: 28px; margin-top: 36px;
    grid-template-columns: 1.2fr 1fr;
    align-items: end;
  }}
  @media (max-width: 800px) {{
    .hero {{ grid-template-columns: 1fr; }}
  }}
  .stat-main {{
    background: linear-gradient(145deg, {ZEPTO_DARK} 0%, #2b1750 60%, {ZEPTO_PURPLE_DEEP} 100%);
    border: 0; border-radius: 22px;
    padding: 28px 30px 32px; color: #fff;
    box-shadow: 0 16px 40px rgba(26, 26, 46, 0.22);
    animation: rise 0.7s ease-out both;
  }}
  .stat-main .label {{
    text-transform: uppercase; letter-spacing: 0.14em; font-size: 0.72rem;
    font-weight: 700; color: #d8b4fe; margin: 0 0 8px;
  }}
  .stat-main .value {{
    font-size: clamp(3.6rem, 10vw, 5.5rem);
    font-weight: 800; letter-spacing: -0.05em; line-height: 0.95;
    margin: 0; color: #fff;
  }}
  .stat-main .meta {{
    margin: 14px 0 0; color: rgba(255,255,255,0.75); font-size: 0.98rem;
  }}
  .stat-main .meta strong {{ color: #fff; font-weight: 700; }}
  .side {{
    display: grid; gap: 12px;
    animation: rise 0.7s ease-out 0.12s both;
  }}
  .chip {{
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 14px 18px;
    display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
    box-shadow: 0 4px 14px rgba(139, 92, 246, 0.06);
  }}
  .chip span {{ color: var(--muted); font-size: 0.9rem; }}
  .chip b {{
    font-size: 1.45rem; font-weight: 800; letter-spacing: -0.02em; color: var(--accent-deep);
  }}
  .actions {{
    margin-top: 22px; display: flex; flex-wrap: wrap; gap: 12px;
    animation: rise 0.7s ease-out 0.2s both;
  }}
  .actions a {{
    display: inline-flex; align-items: center; gap: 8px;
    text-decoration: none; font-weight: 700; font-size: 0.95rem;
    padding: 12px 18px; border-radius: 999px;
    transition: transform 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
  }}
  .actions a.primary {{
    background: var(--accent); color: #fff;
    box-shadow: 0 8px 20px rgba(139, 92, 246, 0.35);
  }}
  .actions a.primary:hover {{ transform: translateY(-1px); background: var(--accent-deep); }}
  .actions a.ghost {{
    background: rgba(255,255,255,0.7); color: var(--ink); border: 1px solid var(--line);
  }}
  .actions a.ghost:hover {{ background: #fff; }}
  .panel {{
    margin-top: 40px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 8px 4px 12px;
    animation: rise 0.7s ease-out 0.28s both;
    overflow: auto;
    box-shadow: 0 8px 24px rgba(139, 92, 246, 0.08);
  }}
  .panel h2 {{
    font-size: 1.25rem; margin: 16px 22px 8px; font-weight: 800; color: var(--ink);
  }}
  .panel p.hint {{
    margin: 0 22px 14px; color: var(--muted); font-size: 0.92rem;
  }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 0.94rem;
  }}
  th, td {{
    text-align: left; padding: 12px 16px; border-top: 1px solid var(--line);
  }}
  th {{
    color: var(--muted); font-weight: 700; font-size: 0.78rem;
    text-transform: uppercase; letter-spacing: 0.06em;
  }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.empty {{ text-align: center; color: var(--muted); padding: 28px; }}
  a {{ color: var(--accent-deep); }}
  footer {{
    margin-top: 28px; color: var(--muted); font-size: 0.85rem;
  }}
  @keyframes rise {{
    from {{ opacity: 0; transform: translateY(12px); }}
    to {{ opacity: 1; transform: none; }}
  }}
"""
