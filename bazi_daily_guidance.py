#!/usr/bin/env python3
"""
Bazi Daily Guidance — sends Iris a short daily email naming today's actual
day pillar (Heavenly Stem + Earthly Branch), its Ten God relationship to her
Day Master (辛 Yin Metal), and how it lands on her specific natal chart.

Mirrors the send mechanism used by tackle-bot's mission_fishing_report.py:
plain SMTP via a Gmail App Password stored as a GitHub Actions secret, so the
email lands directly in the inbox with no draft/click step required.

The day-pillar math (Julian Day Number -> sexagenary cycle index) is fixed
arithmetic, not guesswork — verified against cantian.ai for two known dates:
  2026-07-08 -> Gui-Wei (癸未), 2026-07-09 -> Jia-Shen (甲申), Nayin "Spring Water".
Ten God mapping and natal-chart facts below are sourced from chart-profile.md
in the "Bazi Daily Guide" project (AstroBazi reading) — never recomputed.
"""

import argparse
import smtplib
import os
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Natal chart (fixed facts — from chart-profile.md, do not alter)
# ---------------------------------------------------------------------------
DAY_MASTER = "辛"  # Yin Metal
NATAL_BRANCHES = {"子": "Year", "戌": "Month", "巳": "Day & Hour (doubled)"}
NATAL_STEMS_WOOD_DOUBLED = "甲"  # Year + Month stems, both Yang Wood

# ---------------------------------------------------------------------------
# Sexagenary (60 Jiazi) reference data
# ---------------------------------------------------------------------------
STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
STEM_PINYIN = ["Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"]

BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
BRANCH_PINYIN = ["Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"]

# Primary (dominant) hidden stem for each branch — used for the branch's Ten God read.
BRANCH_PRIMARY_HIDDEN = {
    "子": "癸", "丑": "己", "寅": "甲", "卯": "乙", "辰": "戊", "巳": "丙",
    "午": "丁", "未": "己", "申": "庚", "酉": "辛", "戌": "戊", "亥": "壬",
}

# Six Clashes (六冲) and Six Combinations (六合)
SIX_CLASH = {"子": "午", "丑": "未", "寅": "申", "卯": "酉", "辰": "戌", "巳": "亥"}
SIX_CLASH.update({v: k for k, v in SIX_CLASH.items()})
SIX_COMBINE = {"子": "丑", "寅": "亥", "卯": "戌", "辰": "酉", "巳": "申", "午": "未"}
SIX_COMBINE.update({v: k for k, v in SIX_COMBINE.items()})

# Ten God relative to a Yin Metal (辛) Day Master, keyed by stem.
# element / polarity reasoning:
#   same element        -> Friend (same polarity) / Rob Wealth (opposite polarity)
#   DM produces (Water)  -> Eating God (same polarity) / Hurting Officer (opposite)
#   DM controls (Wood)   -> Indirect Wealth (same polarity) / Direct Wealth (opposite)
#   controls DM (Fire)   -> Seven Killings (same polarity) / Direct Officer (opposite)
#   produces DM (Earth)  -> Indirect Resource (same polarity) / Direct Resource (opposite)
TEN_GOD = {
    "甲": ("Direct Wealth", "wealth"),
    "乙": ("Indirect Wealth", "wealth"),
    "丙": ("Direct Officer", "officer"),
    "丁": ("Seven Killings", "officer"),
    "戊": ("Direct Resource", "resource"),
    "己": ("Indirect Resource", "resource"),
    "庚": ("Rob Wealth", "friend"),
    "辛": ("Friend", "friend"),
    "壬": ("Hurting Officer", "output"),
    "癸": ("Eating God", "output"),
}

# Nayin (纳音) — 30 names, each covering 2 consecutive pillars in the 60-cycle.
NAYIN_NAMES = [
    "Sea Gold", "Hearth Fire", "Great Forest Wood", "Roadside Earth", "Sword Edge Gold",
    "Mountain Top Fire", "Valley Stream Water", "City Wall Earth", "White Wax Metal", "Willow Wood",
    "Spring Water", "Roof Top Earth", "Thunderbolt Fire", "Pine Cypress Wood", "Long River Water",
    "Sand Gold", "Mountain Foot Fire", "Plain Wood", "Wall Earth", "Gold Foil Metal",
    "Lamp Fire", "Sky River Water", "Highway Earth", "Bracelet Metal", "Mulberry Wood",
    "Great Stream Water", "Sand Earth", "Sky Fire", "Pomegranate Wood", "Great Sea Water",
]

MANTRA_CONTAINMENT = "I choose which weight becomes mine to carry."
MANTRA_RETURN = "I return to the water that is already mine."


def julian_day_number(y: int, m: int, d: int) -> int:
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return (
        d
        + (153 * mm + 2) // 5
        + 365 * yy
        + yy // 4
        - yy // 100
        + yy // 400
        - 32045
    )


def sexagenary_index(d: date) -> int:
    """Index 0-59 into the 60 Jiazi cycle. Calibrated + verified against
    cantian.ai: 2026-07-09 (JDN 2461231) = index 20 (Jia-Shen)."""
    jdn = julian_day_number(d.year, d.month, d.day)
    return (jdn + 49) % 60


def get_day_pillar(d: date):
    i = sexagenary_index(d)
    stem_i, branch_i = i % 10, i % 12
    stem, branch = STEMS[stem_i], BRANCHES[branch_i]
    nayin = NAYIN_NAMES[i // 2]
    return stem, branch, nayin


def ten_god_text(stem_or_hidden: str) -> str:
    name, _ = TEN_GOD[stem_or_hidden]
    return name


def build_narrative(stem: str, branch: str, nayin: str) -> str:
    hidden = BRANCH_PRIMARY_HIDDEN[branch]
    stem_god_name, stem_axis = TEN_GOD[stem]
    branch_god_name, branch_axis = TEN_GOD[hidden]

    lines = []
    lines.append(
        f"Today is a {STEM_PINYIN[STEMS.index(stem)]}-{BRANCH_PINYIN[BRANCHES.index(branch)]} "
        f"({stem}{branch}) day."
    )

    # Day stem read
    if stem_axis == "wealth" and stem == NATAL_STEMS_WOOD_DOUBLED:
        lines.append(
            f"The {stem} (day stem) is your {stem_god_name} star — the same channel as the "
            f"doubled Yang Wood already pressing on your Metal self (both your Year and Month "
            f"stems are also {stem}). Today amplifies what's already structurally there: expect "
            f"asks, requests, things wanting something from you, with a bit more force than usual."
        )
    elif stem_axis == "wealth":
        lines.append(
            f"The {stem} (day stem) is your {stem_god_name} star — asks and requests on you today, "
            f"lighter than your natal doubled-Wood pressure but the same family of demand."
        )
    elif stem_axis == "officer":
        lines.append(
            f"The {stem} (day stem) is your {stem_god_name} star — your pressure axis is directly "
            f"activated today, the same force as the doubled Fire under your Day Master and Hour. "
            f"Expect more heat, more being asked to perform or hold a line."
        )
    elif stem_axis == "resource":
        lines.append(
            f"The {stem} (day stem) is your {stem_god_name} star — grounding, supportive. Your Metal "
            f"self is at ease held by Earth; today leans toward that ease rather than pressure."
        )
    elif stem_axis == "output":
        lines.append(
            f"The {stem} (day stem) is your {stem_god_name} star — an expression channel. Days like "
            f"this favor letting something out rather than holding it: writing, cooking, a real "
            f"conversation."
        )
    else:  # friend
        lines.append(
            f"The {stem} (day stem) is your {stem_god_name} star — peer energy, the same element as "
            f"your Day Master. More backup today, more capacity to hold whatever comes without being "
            f"melted down by it."
        )

    # Day branch read
    if branch_axis == "officer":
        lines.append(
            f"The {branch} (day branch, hidden {hidden}) carries the same {branch_god_name} pressure "
            f"into the day — a second helping of the Fire axis rather than relief from it."
        )
    elif branch_axis == "friend":
        lines.append(
            f"The {branch} (day branch, hidden {hidden}) is Metal meeting Metal, not the Fire that "
            f"usually does the pressing — more structural room to absorb today's demands."
        )
    elif branch_axis in ("resource", "output"):
        lines.append(
            f"The {branch} (day branch, hidden {hidden}) leans supportive/relieving rather than "
            f"pressuring — {branch_god_name.lower()} energy underneath today."
        )
    else:  # wealth
        lines.append(
            f"The {branch} (day branch, hidden {hidden}) adds a second, quieter layer of "
            f"{branch_god_name.lower()} demand underneath today's stem."
        )

    # Clash / combine against natal branches
    for natal_branch, label in NATAL_BRANCHES.items():
        if SIX_CLASH.get(branch) == natal_branch:
            lines.append(
                f"Today's branch clashes with your natal {natal_branch} ({label}) — expect that "
                f"pillar's theme to feel shaken loose or more volatile than usual today."
            )
        elif SIX_COMBINE.get(branch) == natal_branch:
            lines.append(
                f"Today's branch combines with your natal {natal_branch} ({label}) — a pull toward "
                f"settling or merging around whatever that pillar represents for you."
            )

    # Nayin note
    if "Water" in nayin:
        lines.append(
            f"This day's nayin is {nayin} — the exact element your chart runs short on. Worth "
            f"noticing if something today naturally cools or drains the day's pressure (real rest, "
            f"time near water) rather than forcing through it."
        )
    elif "Earth" in nayin:
        lines.append(
            f"This day's nayin is {nayin} — more of the grounding your Metal self leans on."
        )

    # Mantra
    pressure_today = stem_axis in ("wealth", "officer") or branch_axis in ("wealth", "officer")
    mantra = MANTRA_CONTAINMENT if pressure_today else MANTRA_RETURN
    lines.append(f'Before you open your inbox this morning, say once: "{mantra}"')

    return "\n\n".join(lines)


def datetime_now_pacific_date() -> date:
    from datetime import datetime
    return datetime.now(ZoneInfo("America/Vancouver")).date()


def send_email(subject: str, body: str):
    gmail_address = os.environ["GMAIL_ADDRESS"]
    send_to = os.environ["SEND_TO"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = send_to
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, [send_to], msg.as_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="send even if already sent today")
    args = parser.parse_args()

    today = datetime_now_pacific_date()

    stem, branch, nayin = get_day_pillar(today)
    body = build_narrative(stem, branch, nayin)
    subject = f"Your Bazi Daily Guide — {today.isoformat()}"

    print(f"Day pillar: {stem}{branch}  Nayin: {nayin}")
    print(body)

    send_email(subject, body)
    print("Sent.")


if __name__ == "__main__":
    main()
