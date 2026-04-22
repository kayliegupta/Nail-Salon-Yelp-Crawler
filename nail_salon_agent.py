"""
====================================================
  Nail Salon Lead Generator — Bay Area AI Agent
  v2 — with deduplication, city rotation & HTML output
====================================================
Finds Bay Area nail salons WITHOUT a website on Yelp,
generates AI outreach notes, and saves a beautiful
HTML report. Remembers past leads to never repeat.

SETUP:
  pip install openai requests python-dotenv

  Create a .env file in the same folder:
    YELP_API_KEY=your_yelp_key_here
    OPENAI_API_KEY=your_openai_key_here

  Get a free Yelp key at:
    https://www.yelp.com/developers/v3/manage_app
"""

import os
import csv
import json
import time
import requests
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────

YELP_API_KEY   = os.getenv("YELP_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Full Bay Area city pool — agent rotates through these automatically
ALL_CITIES = [
    "San Francisco, CA",
    "Oakland, CA",
    "San Jose, CA",
    "Fremont, CA",
    "Berkeley, CA",
    "Palo Alto, CA",
    "Santa Clara, CA",
    "Sunnyvale, CA",
    "Hayward, CA",
    "Daly City, CA",
    "Richmond, CA",
    "Walnut Creek, CA",
    "Concord, CA",
    "San Mateo, CA",
    "Redwood City, CA",
    "Mountain View, CA",
    "Milpitas, CA",
    "Union City, CA",
]

MAX_LEADS        = 10
RESULTS_PER_CITY = 20
YELP_SEARCH_URL  = "https://api.yelp.com/v3/businesses/search"

OUTPUT_DIR    = os.path.dirname(os.path.abspath(__file__))
HTML_OUTPUT   = os.path.join(OUTPUT_DIR, "nail_salon_leads.html")
CSV_OUTPUT    = os.path.join(OUTPUT_DIR, "nail_salon_leads.csv")
SEEN_FILE     = os.path.join(OUTPUT_DIR, ".seen_salons.json")
CITY_FILE     = os.path.join(OUTPUT_DIR, ".city_state.json")

# ── Persistence helpers ───────────────────────────────────────────────────────

def load_seen() -> set:
    """Load previously found salon IDs."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def load_city_state() -> dict:
    """Load which cities have been used and how many results were found."""
    if os.path.exists(CITY_FILE):
        with open(CITY_FILE) as f:
            return json.load(f)
    return {"exhausted": [], "offsets": {}}

def save_city_state(state: dict):
    with open(CITY_FILE, "w") as f:
        json.dump(state, f)

def get_city_order(state: dict) -> list:
    """
    Agentic city rotation:
    - Skip exhausted cities
    - Prioritize cities with remaining offset (partially searched)
    - Fall back to fresh cities
    """
    exhausted = set(state.get("exhausted", []))
    offsets   = state.get("offsets", {})
    available = [c for c in ALL_CITIES if c not in exhausted]

    partial = [c for c in available if c in offsets and offsets[c] > 0]
    fresh   = [c for c in available if c not in offsets]
    return partial + fresh

# ── Yelp helpers ──────────────────────────────────────────────────────────────

def search_yelp(city: str, offset: int = 0) -> list:
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    params  = {
        "term":     "nail salon",
        "location": city,
        "limit":    RESULTS_PER_CITY,
        "offset":   offset,
    }
    try:
        resp = requests.get(YELP_SEARCH_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("businesses", [])
    except requests.exceptions.HTTPError as e:
        print(f"  [Yelp error] {city}: {e}")
        return []
    except Exception as e:
        print(f"  [Network error] {city}: {e}")
        return []

def has_website(biz_id: str) -> bool:
    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    try:
        resp = requests.get(
            f"https://api.yelp.com/v3/businesses/{biz_id}",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return bool(resp.json().get("website"))
    except Exception:
        return False

def extract_lead(biz: dict) -> dict:
    loc  = biz.get("location", {})
    addr = ", ".join(filter(None, [
        loc.get("address1", ""),
        loc.get("city", ""),
        loc.get("state", ""),
        loc.get("zip_code", ""),
    ]))
    cats = ", ".join(c["title"] for c in biz.get("categories", []))
    return {
        "id":           biz.get("id", ""),
        "name":         biz.get("name", "N/A"),
        "phone":        biz.get("display_phone", "N/A"),
        "address":      addr or "N/A",
        "city":         loc.get("city", "N/A"),
        "rating":       biz.get("rating", "N/A"),
        "review_count": biz.get("review_count", 0),
        "categories":   cats or "Nail Salon",
        "yelp_url":     biz.get("url", "#"),
    }

# ── OpenAI agent ──────────────────────────────────────────────────────────────

client = OpenAI(api_key=OPENAI_API_KEY)

def generate_outreach(lead: dict) -> str:
    prompt = f"""
You are a friendly freelance web developer who specializes in helping small businesses.
Write a SHORT, warm, personalized cold-outreach message (3-4 sentences MAX, under 80 words)
to the owner of a nail salon that has no website.

Salon details:
- Name: {lead['name']}
- City: {lead['city']}
- Yelp rating: {lead['rating']} stars ({lead['review_count']} reviews)
- Categories: {lead['categories']}

The message should:
1. Reference their salon name and city naturally.
2. Briefly explain why not having a website is costing them customers.
3. End with a soft call-to-action (free consult or quick chat).
No subject line. No sign-off needed.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.85,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate outreach note: {e}"

# ── HTML output ───────────────────────────────────────────────────────────────

def save_html(leads: list, run_number: int):
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    cards_html = ""

    for i, lead in enumerate(leads, 1):
        rating     = lead["rating"]
        full_stars = int(rating) if isinstance(rating, (int, float)) else 0
        stars      = "★" * full_stars + "☆" * (5 - full_stars)
        cards_html += f"""
        <div class="card" style="animation-delay: {i * 0.07}s">
            <div class="card-header">
                <div class="lead-number">{i:02d}</div>
                <div class="card-title-block">
                    <h2 class="salon-name">{lead['name']}</h2>
                    <span class="city-tag">{lead['city']}</span>
                </div>
                <div class="no-site-badge">No Website</div>
            </div>
            <div class="card-body">
                <div class="info-row">
                    <div class="info-item">
                        <span class="info-icon">📞</span>
                        <div>
                            <span class="info-label">Phone</span>
                            <span class="info-value">{lead['phone']}</span>
                        </div>
                    </div>
                    <div class="info-item">
                        <span class="info-icon">📍</span>
                        <div>
                            <span class="info-label">Address</span>
                            <span class="info-value">{lead['address']}</span>
                        </div>
                    </div>
                    <div class="info-item">
                        <span class="info-icon">⭐</span>
                        <div>
                            <span class="info-label">Rating</span>
                            <span class="info-value stars">{stars} <em>({lead['review_count']} reviews)</em></span>
                        </div>
                    </div>
                    <div class="info-item">
                        <span class="info-icon">🔗</span>
                        <div>
                            <span class="info-label">Yelp Page</span>
                            <a class="yelp-link" href="{lead['yelp_url']}" target="_blank">View on Yelp →</a>
                        </div>
                    </div>
                </div>
                <div class="outreach-block">
                    <div class="outreach-label">✍️ AI Outreach Note</div>
                    <p class="outreach-text">{lead['outreach']}</p>
                </div>
            </div>
        </div>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nail Salon Leads — Run #{run_number}</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'DM Sans', sans-serif;
            background: #fdf6f0;
            color: #1a1a1a;
            min-height: 100vh;
            padding: 0 0 80px;
        }}

        .header {{
            background: linear-gradient(135deg, #1a1a1a 0%, #2d1f1f 100%);
            color: white;
            padding: 52px 40px 60px;
            position: relative;
            overflow: hidden;
        }}
        .header::before {{
            content: '💅';
            position: absolute;
            right: 60px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 120px;
            opacity: 0.07;
        }}
        .header::after {{
            content: '';
            position: absolute;
            bottom: -1px; left: 0; right: 0;
            height: 40px;
            background: #fdf6f0;
            clip-path: ellipse(55% 100% at 50% 100%);
        }}
        .header-inner {{
            max-width: 860px;
            margin: 0 auto;
            position: relative;
            z-index: 1;
        }}
        .header-eyebrow {{
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.2em;
            text-transform: uppercase;
            color: #e8b4a0;
            margin-bottom: 14px;
        }}
        .header h1 {{
            font-family: 'DM Serif Display', serif;
            font-size: clamp(30px, 5vw, 46px);
            font-weight: 400;
            line-height: 1.15;
            margin-bottom: 20px;
        }}
        .header h1 span {{ color: #e8b4a0; }}
        .header-meta {{
            display: flex;
            gap: 24px;
            flex-wrap: wrap;
            font-size: 13px;
            color: rgba(255,255,255,0.5);
        }}
        .header-meta strong {{ color: rgba(255,255,255,0.85); font-weight: 500; }}

        .stats-bar {{
            max-width: 860px;
            margin: 32px auto 0;
            padding: 0 24px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .stat-pill {{
            background: white;
            border: 1px solid #ede0d8;
            border-radius: 100px;
            padding: 8px 18px;
            font-size: 13px;
            font-weight: 500;
            color: #5a3e35;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }}
        .stat-pill span {{ color: #c0614a; font-weight: 600; }}

        .leads-container {{
            max-width: 860px;
            margin: 28px auto 0;
            padding: 0 24px;
            display: flex;
            flex-direction: column;
            gap: 18px;
        }}

        .card {{
            background: white;
            border-radius: 16px;
            border: 1px solid #ede0d8;
            box-shadow: 0 2px 16px rgba(0,0,0,0.05);
            overflow: hidden;
            opacity: 0;
            transform: translateY(16px);
            animation: slideUp 0.4s ease forwards;
        }}
        @keyframes slideUp {{
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .card-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 18px 24px;
            border-bottom: 1px solid #f5ede8;
            background: linear-gradient(to right, #fffaf7, white);
        }}
        .lead-number {{
            font-family: 'DM Serif Display', serif;
            font-size: 30px;
            color: #dcc4b8;
            line-height: 1;
            min-width: 38px;
        }}
        .card-title-block {{ flex: 1; min-width: 0; }}
        .salon-name {{
            font-family: 'DM Serif Display', serif;
            font-size: 20px;
            font-weight: 400;
            color: #1a1a1a;
            line-height: 1.25;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .city-tag {{
            font-size: 12px;
            font-weight: 500;
            color: #8a6a5e;
            letter-spacing: 0.04em;
            margin-top: 3px;
            display: block;
        }}
        .no-site-badge {{
            background: #fff0ec;
            color: #c0614a;
            border: 1px solid #f5c8bc;
            border-radius: 100px;
            padding: 5px 14px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
            flex-shrink: 0;
        }}

        .card-body {{ padding: 18px 24px; }}

        .info-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
            margin-bottom: 18px;
        }}
        .info-item {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
        }}
        .info-icon {{ font-size: 16px; margin-top: 2px; flex-shrink: 0; }}
        .info-label {{
            display: block;
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: #b09a90;
            margin-bottom: 3px;
        }}
        .info-value {{
            font-size: 14px;
            color: #2a2a2a;
            line-height: 1.4;
        }}
        .info-value.stars {{ color: #c0614a; }}
        .info-value.stars em {{
            color: #8a6a5e;
            font-style: normal;
            font-size: 12px;
        }}
        .yelp-link {{
            font-size: 14px;
            color: #c0614a;
            text-decoration: none;
            font-weight: 500;
            border-bottom: 1px solid transparent;
            transition: border-color 0.15s;
        }}
        .yelp-link:hover {{ border-color: #c0614a; }}

        .outreach-block {{
            background: #fdf8f5;
            border: 1px solid #ede0d8;
            border-left: 3px solid #e8b4a0;
            border-radius: 10px;
            padding: 14px 18px;
        }}
        .outreach-label {{
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #b09a90;
            margin-bottom: 8px;
        }}
        .outreach-text {{
            font-size: 14px;
            line-height: 1.7;
            color: #3a2e2a;
        }}

        .footer {{
            max-width: 860px;
            margin: 48px auto 0;
            padding: 0 24px;
            text-align: center;
            font-size: 12px;
            color: #b09a90;
            line-height: 1.8;
        }}
        .footer strong {{ color: #8a6a5e; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-inner">
            <div class="header-eyebrow">Freelance Web Dev · Lead Report</div>
            <h1>Bay Area Nail Salons<br><span>Without a Website</span></h1>
            <div class="header-meta">
                <span>🗓 {timestamp}</span>
                <span>📋 Run <strong>#{run_number}</strong></span>
                <span>📍 <strong>{len(leads)} new leads</strong> this run</span>
            </div>
        </div>
    </div>

    <div class="stats-bar">
        <div class="stat-pill">🎯 <span>{len(leads)}</span> leads this run</div>
        <div class="stat-pill">🏙 Bay Area cities searched</div>
        <div class="stat-pill">🤖 AI outreach included</div>
        <div class="stat-pill">✅ Zero duplicates</div>
    </div>

    <div class="leads-container">
        {cards_html}
    </div>

    <div class="footer">
        <p>Generated by <strong>Nail Salon Lead Agent v2</strong><br>
        Each lead confirmed to have no website on Yelp · {timestamp}</p>
    </div>
</body>
</html>"""

    with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)


# ── CSV append ────────────────────────────────────────────────────────────────

def append_csv(leads: list):
    fields        = ["name", "phone", "address", "city", "rating", "review_count", "yelp_url", "outreach"]
    write_header  = not os.path.exists(CSV_OUTPUT)
    with open(CSV_OUTPUT, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(leads)


# ── Main agent ────────────────────────────────────────────────────────────────

def run_agent():
    print("\n💅  Nail Salon Lead Generator — Bay Area  v2")
    print("=" * 48)

    if not YELP_API_KEY:
        print("\n❌  YELP_API_KEY not set. Add it to your .env file.")
        print("    Get a free key → https://www.yelp.com/developers/v3/manage_app\n")
        return
    if not OPENAI_API_KEY:
        print("\n❌  OPENAI_API_KEY not set. Add it to your .env file.\n")
        return

    seen       = load_seen()
    city_state = load_city_state()
    run_number = city_state.get("run_number", 0) + 1
    city_state["run_number"] = run_number

    print(f"\n🧠  Memory: {len(seen)} salons seen in past runs.")
    print(f"🔁  This is run #{run_number}\n")

    city_order = get_city_order(city_state)
    if not city_order:
        print("♻️  All cities exhausted — resetting for a fresh cycle.")
        city_state = {"exhausted": [], "offsets": {}, "run_number": run_number}
        city_order = ALL_CITIES[:]

    leads    = []
    new_seen = set()

    for city in city_order:
        if len(leads) >= MAX_LEADS:
            break

        offset = city_state.get("offsets", {}).get(city, 0)
        print(f"📍  {city} (offset {offset}) ...")
        businesses = search_yelp(city, offset=offset)

        if not businesses:
            print(f"    ↳ No results — marking exhausted, rotating to next city.")
            city_state.setdefault("exhausted", [])
            if city not in city_state["exhausted"]:
                city_state["exhausted"].append(city)
            continue

        for biz in businesses:
            if len(leads) >= MAX_LEADS:
                break

            biz_id = biz.get("id", "")
            name   = biz.get("name", "Unknown")

            if biz_id in seen:
                print(f"    ⏭  {name} — already seen")
                continue

            print(f"    Checking: {name} ...", end=" ", flush=True)
            time.sleep(0.35)

            if has_website(biz_id):
                print("✅ has website")
                new_seen.add(biz_id)
                continue

            print("🚫 no website — LEAD!")
            lead = extract_lead(biz)
            print(f"    ✍️  Writing outreach note ...")
            lead["outreach"] = generate_outreach(lead)
            leads.append(lead)
            new_seen.add(biz_id)
            time.sleep(0.3)

        city_state.setdefault("offsets", {})[city] = offset + len(businesses)

        if len(businesses) < RESULTS_PER_CITY:
            if city not in city_state.get("exhausted", []):
                city_state.setdefault("exhausted", []).append(city)
                print(f"    ↳ Fully searched — will rotate away next run.")

    seen.update(new_seen)
    save_seen(seen)
    save_city_state(city_state)

    if not leads:
        print("\n⚠️  No new leads this run. Agent will try new cities next run automatically.")
        return

    save_html(leads, run_number)
    append_csv(leads)

    print(f"\n{'=' * 48}")
    print(f"✅  Done! {len(leads)} new leads found.")
    print(f"   🌐 HTML report  → {HTML_OUTPUT}")
    print(f"   📊 CSV (master) → {CSV_OUTPUT}")
    print(f"   🧠 Total tracked: {len(seen)} salons")
    print(f"{'=' * 48}\n")

    print("── PREVIEW ──────────────────────────────────────")
    for i, lead in enumerate(leads[:3], 1):
        print(f"\n{i}. {lead['name']}")
        print(f"   📞 {lead['phone']}  |  📍 {lead['city']}")
        print(f"   🔗 {lead['yelp_url'][:70]}")
        print(f"   ✍️  {lead['outreach'][:100]}...")
    if len(leads) > 3:
        print(f"\n   ... and {len(leads) - 3} more in the HTML report.")
    print()


if __name__ == "__main__":
    run_agent()