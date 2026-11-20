#!/usr/bin/env python3
"""The World Today - 20 November 2026.

Draws a one-page newspaper front page summing up the day's world news
and writes it to $MAKEFUN_OUTPUT_DIR/entry.png (default: out/entry.png).

Standard library + Pillow only. No network, no timestamps, no randomness:
two runs write identical bytes.

Layout never aborts: there is no hard exit on overflow. If the content
runs past the vertical budget, the fonts shrink in 2 px steps and the
page is drawn again, down to sane minimum sizes; even at the minimum
the image is still written.
"""

import io
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 768, 1024
MARGIN = 26
CW = W - 2 * MARGIN  # 716 px of content width
BUDGET_Y = 900       # content (last story) must end at or above this
HERO_H = 128         # displayed height of the hero photo banner
MAX_BYTES = 1048576  # 1 MiB gate limit

PAPER = (246, 241, 231)
INK = (25, 21, 18)
MUTED = (74, 66, 56)
RED = (143, 29, 22)
HAIRLINE = (185, 172, 147)
BORDER = (122, 94, 58)
RULE = (25, 21, 18)

MASTHEAD = "THE WORLD TODAY"
DATELINE = "FRIDAY \u00b7 20 NOVEMBER 2026"
FOOTER = "Sources: Reuters \u00b7 BBC \u00b7 AP \u00b7 IMD \u00b7 CNN \u2014 20 November 2026"

# (headline, caption, is_lead)
STORIES = [
    ("World court finds Myanmar guilty of genocide",
     "9\u20136 ruling \u2014 first state ever held responsible for genocide",
     True),
    ("Kyiv bridges hit overnight",
     "Missile strikes damage crossings over the Dnipro; traffic cut",
     False),
    ("Trump, Xi, Putin issue reported peace declaration",
     "Four-point text reported from Shenzhen; no mention of Ukraine",
     False),
    ("Taiwan stocks in freefall",
     "Taiex \u22126% today, \u221217% in a week \u2014 worst week since 1991",
     False),
    ("Cyclone Akvan hits India",
     "300,000+ evacuated as storm makes landfall near Gopalpur",
     False),
    ("GTA VI sells a reported 24.6m copies on day one",
     "$2.36bn in day-one sales, est. \u2014 industry estimates",
     False),
    ("Houthi missile hits Riyadh's tallest tower",
     "Windows shattered across 7\u20138 floors; no casualties reported",
     False),
    ("COP31 draft drops fossil-fuel language",
     "80 paragraphs cut as talks run into their final day",
     False),
]

SERIF_BOLD = ["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"]
SERIF = ["DejaVuSerif.ttf", "LiberationSerif-Regular.ttf"]
SANS_BOLD = ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
SANS = ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"]

FONT_DIRS = []
if os.environ.get("NEWS_FONT_DIR"):
    # Explicit override: only this directory is searched, so a test can
    # force Liberation-only or no fonts at all (then load_default).
    FONT_DIRS.append(os.environ["NEWS_FONT_DIR"])
else:
    FONT_DIRS += [
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation",
        "/usr/share/fonts/truetype/liberation2",
        "/usr/share/fonts",
    ]


def load_font(names, size):
    """Try each candidate file in turn, then fall back to the default font."""
    for directory in FONT_DIRS:
        for name in names:
            path = Path(directory) / name
            if path.is_file():
                try:
                    return ImageFont.truetype(str(path), size)
                except Exception:
                    continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def wrap(draw, text, font, max_w):
    """Greedy word wrap; a single over-long word still goes on its own line."""
    lines = []
    current = ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if not current or draw.textlength(trial, font=font) <= max_w:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_centered(draw, y, text, font, fill, leading):
    """Draw (possibly wrapped) text centred; return the y below it."""
    for line in wrap(draw, text, font, CW):
        draw.text((W / 2, y), line, font=font, fill=fill, anchor="ma")
        y += leading
    return y


def draw_left(draw, y, text, font, fill, leading):
    """Draw (possibly wrapped) text left-aligned; return the y below it."""
    for line in wrap(draw, text, font, CW):
        draw.text((MARGIN, y), line, font=font, fill=fill, anchor="la")
        y += leading
    return y


def load_hero():
    """Hero photo at content width, centre-cropped to the banner height.

    Falls back to a plain dusk-coloured panel if scene.png is missing,
    so a missing photo can never stop the render.
    """
    for candidate in (Path(__file__).resolve().parent / "scene.png",
                      Path.cwd() / "scene.png"):
        if candidate.is_file():
            photo = Image.open(candidate).convert("RGB")
            scaled_h = max(1, round(photo.height * CW / photo.width))
            photo = photo.resize((CW, scaled_h), Image.LANCZOS)
            if photo.height > HERO_H:
                top = (photo.height - HERO_H) // 2
                photo = photo.crop((0, top, CW, top + HERO_H))
            return photo
    return Image.new("RGB", (CW, HERO_H), (58, 74, 110))


def render(sizes):
    """Draw the whole page at the given font sizes; return (image, y_end).

    y_end is the y just below the last story's caption, before the footer.
    Nothing in here raises for layout reasons.
    """
    img = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(img)

    masthead_font = load_font(SERIF_BOLD, sizes["masthead"])
    # Shrink the masthead until it fits the content width.
    while (sizes["masthead"] > 40
           and draw.textlength(MASTHEAD, font=masthead_font) > CW):
        sizes["masthead"] -= 2
        masthead_font = load_font(SERIF_BOLD, sizes["masthead"])
    date_font = load_font(SANS_BOLD, sizes["date"])
    lead_font = load_font(SERIF_BOLD, sizes["lead"])
    head_font = load_font(SANS_BOLD, sizes["head"])
    cap_font = load_font(SANS, sizes["cap"])
    foot_font = load_font(SANS, sizes["foot"])

    mast_lead = round(sizes["masthead"] * 1.15)
    date_lead = round(sizes["date"] * 1.25)
    lead_lead = round(sizes["lead"] * 1.22)
    head_lead = round(sizes["head"] * 1.18)
    cap_lead = round(sizes["cap"] * 1.25)
    foot_lead = round(sizes["foot"] * 1.25)

    y = MARGIN

    # Masthead + dateline + two rules.
    y = draw_centered(draw, y, MASTHEAD, masthead_font, INK, mast_lead)
    y += 4
    y = draw_centered(draw, y, DATELINE, date_font, RED, date_lead)
    y += 8
    draw.line([(MARGIN, y), (W - MARGIN, y)], fill=RULE, width=2)
    y += 6
    draw.line([(MARGIN, y), (W - MARGIN, y)], fill=RULE, width=2)
    y += 10

    # Hero photo with a brown border.
    hero = load_hero()
    img.paste(hero, (MARGIN, y))
    draw.rectangle([MARGIN, y, MARGIN + CW - 1, y + hero.height - 1],
                   outline=BORDER, width=2)
    y += hero.height + 10

    # Lead story, centred.
    lead_head, lead_cap, _ = STORIES[0]
    y = draw_centered(draw, y, lead_head, lead_font, INK, lead_lead)
    y += 4
    y = draw_centered(draw, y, lead_cap, cap_font, MUTED, cap_lead)
    y += 8

    # The other seven stories, left-aligned, hairline between them.
    for index, (head, cap, _) in enumerate(STORIES[1:]):
        y = draw_left(draw, y, head, head_font, INK, head_lead)
        y += 2
        y = draw_left(draw, y, cap, cap_font, MUTED, cap_lead)
        y += 4
        if index < len(STORIES) - 2:
            draw.line([(MARGIN, y), (W - MARGIN, y)], fill=HAIRLINE, width=1)
            y += 6

    y_end = y

    # Footer, centred below the stories.
    draw_centered(draw, y_end + 14, FOOTER, foot_font, MUTED, foot_lead)
    return img, y_end


def main():
    sizes = {"masthead": 60, "date": 18, "lead": 30,
             "head": 26, "cap": 20, "foot": 15}
    mins = {"lead": 24, "head": 20, "cap": 16}

    # Adaptive loop: shrink the story fonts until the content fits the
    # budget, or the sane minimum sizes are reached. Either way the loop
    # ends with an image being written, never an error.
    while True:
        img, y_end = render(sizes)
        if y_end <= BUDGET_Y:
            break
        if (sizes["head"] <= mins["head"] and sizes["lead"] <= mins["lead"]
                and sizes["cap"] <= mins["cap"]):
            break
        sizes["head"] = max(mins["head"], sizes["head"] - 2)
        sizes["lead"] = max(mins["lead"], sizes["lead"] - 2)
        sizes["cap"] = max(mins["cap"], sizes["cap"] - 2)

    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR") or "out")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "entry.png"

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    if len(data) > MAX_BYTES:
        # Same picture, JPEG bytes under the gate limit (name stays entry.png).
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        data = buf.getvalue()
    out_path.write_bytes(data)
    print(f"final_y={y_end} sizes={sizes} bytes={len(data)} path={out_path}")


if __name__ == "__main__":
    main()
