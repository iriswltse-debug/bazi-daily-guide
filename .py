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
SIX
