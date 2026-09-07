"""One-off asset generator. Pillow is not a runtime dependency."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "happy-path.gif"
W, H = 960, 320
BG = (247, 246, 243)
INK = (31, 31, 31)
MUTED = (232, 230, 225)
ACTIVE = (180, 83, 9)
DONE = (46, 125, 50)
WHITE = (255, 255, 255)

STEPS = [
    ("1  Webhook", "POST /webhook/mock\nCelery runs inbound graph"),
    ("2  Graph", "ingest → … → draft → hitl"),
    ("3  HITL", "Ticket status\nAWAITING_HUMAN"),
    ("4  Approve", "POST /tickets/{id}/approve"),
    ("5  Send", "Mock send · RESOLVED\n(not on inbound spine)"),
]


def _font(size: int):
    for name in ("segoeui.ttf", "SegoeUI.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _frame(step: int) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    title = _font(22)
    body = _font(16)
    small = _font(14)
    draw.text((32, 24), "Happy path — API only (no Streamlit)", fill=INK, font=title)
    box_w = 168
    gap = 16
    x0 = 32
    for i, (label, _) in enumerate(STEPS):
        x = x0 + i * (box_w + gap)
        fill = ACTIVE if i == step else (DONE if i < step else MUTED)
        fg = WHITE if i <= step else INK
        draw.rounded_rectangle((x, 72, x + box_w, 132), radius=8, fill=fill)
        draw.text((x + 12, 92), label, fill=fg, font=small)
        if i < len(STEPS) - 1:
            draw.polygon(
                [(x + box_w + 2, 102), (x + box_w + 12, 92), (x + box_w + 12, 112)],
                fill=INK,
            )
    draw.rounded_rectangle((32, 160, W - 32, 288), radius=8, fill=WHITE, outline=INK, width=2)
    heading, detail = STEPS[step]
    draw.text((48, 176), heading, fill=INK, font=title)
    draw.text((48, 216), detail, fill=INK, font=body)
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames = [_frame(i) for i in range(len(STEPS))]
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=1100,
        loop=0,
        optimize=True,
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
