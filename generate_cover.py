"""
速報版カバー画像生成スクリプト
モダンでクリーンなテック風 1400x1400 カバーアート
"""

import math
import random
from PIL import Image, ImageDraw, ImageFont

# --- 設定 ---
WIDTH, HEIGHT = 1400, 1400
OUTPUT_PATH = "cover.jpg"

# カラーパレット（クリーンなブルー系）
BG_TOP = (12, 20, 50)       # ダークネイビー（上）
BG_BOTTOM = (20, 35, 80)    # ミッドネイビー（下）
ACCENT = (0, 180, 255)      # シアン
ACCENT2 = (80, 120, 255)    # ブルー
HIGHLIGHT = (0, 255, 200)   # ネオングリーン（ポイント）
GRID_COLOR = (25, 40, 80)
TEXT_WHITE = (255, 255, 255)
TEXT_SUB = (160, 200, 230)


def gradient_background(draw: ImageDraw.Draw) -> None:
    """縦グラデーション背景"""
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * ratio)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * ratio)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))


def draw_dot_grid(draw: ImageDraw.Draw) -> None:
    """ドットグリッドパターン（モダン）"""
    spacing = 50
    for x in range(spacing, WIDTH, spacing):
        for y in range(spacing, HEIGHT, spacing):
            dist_center = math.sqrt((x - WIDTH / 2) ** 2 + (y - HEIGHT / 2) ** 2)
            max_dist = math.sqrt((WIDTH / 2) ** 2 + (HEIGHT / 2) ** 2)
            alpha = max(0.05, 0.3 * (1 - dist_center / max_dist))
            color = (
                int(ACCENT[0] * alpha),
                int(ACCENT[1] * alpha),
                int(ACCENT[2] * alpha),
            )
            draw.ellipse([(x - 1, y - 1), (x + 1, y + 1)], fill=color)


def draw_pulse_rings(draw: ImageDraw.Draw) -> None:
    """パルスリング（速報＝電波の象徴）"""
    cx, cy = WIDTH // 2, 380
    for i, r in enumerate(range(60, 300, 40)):
        alpha = max(0.1, 0.5 - i * 0.07)
        color = (
            int(ACCENT[0] * alpha),
            int(ACCENT[1] * alpha),
            int(ACCENT[2] * alpha),
        )
        draw.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            outline=color, width=2,
        )


def draw_signal_bars(draw: ImageDraw.Draw) -> None:
    """シグナルバー（ラジオ/通信の象徴）"""
    cx, cy = WIDTH // 2, 380
    for gr in range(12, 0, -2):
        glow = (HIGHLIGHT[0] // 3, HIGHLIGHT[1] // 3, HIGHLIGHT[2] // 3)
        draw.ellipse([(cx - gr, cy - gr), (cx + gr, cy + gr)], fill=glow)
    draw.ellipse([(cx - 6, cy - 6), (cx + 6, cy + 6)], fill=HIGHLIGHT)


def draw_data_stream(draw: ImageDraw.Draw) -> None:
    """データストリーム装飾（下部）"""
    random.seed(42)
    bar_width = 3
    gap = 4
    total_width = 900
    start_x = (WIDTH - total_width) // 2
    y_center = 1050

    for i in range(total_width // (bar_width + gap)):
        x = start_x + i * (bar_width + gap)
        progress = i / (total_width // (bar_width + gap))
        envelope = math.sin(progress * math.pi) ** 0.5
        h = int(random.uniform(3, 35) * envelope + 2)

        ratio = abs(progress - 0.5) * 2
        r = int(ACCENT[0] * (1 - ratio) + HIGHLIGHT[0] * ratio)
        g = int(ACCENT[1] * (1 - ratio) + HIGHLIGHT[1] * ratio)
        b = int(ACCENT[2] * (1 - ratio) + HIGHLIGHT[2] * ratio)

        draw.rectangle(
            [(x, y_center - h), (x + bar_width, y_center + h)],
            fill=(r, g, b),
        )


def draw_corner_accents(draw: ImageDraw.Draw) -> None:
    """コーナーアクセント装飾"""
    length = 80
    margin = 60
    color = ACCENT
    w = 2
    # 左上
    draw.line([(margin, margin), (margin + length, margin)], fill=color, width=w)
    draw.line([(margin, margin), (margin, margin + length)], fill=color, width=w)
    # 右上
    draw.line([(WIDTH - margin, margin), (WIDTH - margin - length, margin)], fill=color, width=w)
    draw.line([(WIDTH - margin, margin), (WIDTH - margin, margin + length)], fill=color, width=w)
    # 左下
    draw.line([(margin, HEIGHT - margin), (margin + length, HEIGHT - margin)], fill=color, width=w)
    draw.line([(margin, HEIGHT - margin), (margin, HEIGHT - margin - length)], fill=color, width=w)
    # 右下
    draw.line([(WIDTH - margin, HEIGHT - margin), (WIDTH - margin - length, HEIGHT - margin)], fill=color, width=w)
    draw.line([(WIDTH - margin, HEIGHT - margin), (WIDTH - margin, HEIGHT - margin - length)], fill=color, width=w)


def draw_text(draw: ImageDraw.Draw) -> None:
    """メインテキスト描画"""
    FONT_EN = "/System/Library/Fonts/Helvetica.ttc"
    FONT_JP = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
    try:
        font_main_jp = ImageFont.truetype(FONT_JP, 100)
        font_sub_jp = ImageFont.truetype(FONT_JP, 50)
        font_tag = ImageFont.truetype(FONT_JP, 34)
        font_badge = ImageFont.truetype(FONT_EN, 28)
    except (OSError, IOError):
        font_main_jp = ImageFont.load_default()
        font_sub_jp = ImageFont.load_default()
        font_tag = ImageFont.load_default()
        font_badge = ImageFont.load_default()

    # 「テック速報」
    title1 = "テック速報"
    bbox1 = draw.textbbox((0, 0), title1, font=font_main_jp)
    tw1 = bbox1[2] - bbox1[0]
    x1 = (WIDTH - tw1) // 2
    y1 = 530
    for offset in range(10, 0, -2):
        glow = (ACCENT[0] // 5, ACCENT[1] // 5, ACCENT[2] // 5)
        draw.text((x1, y1), title1, font=font_main_jp, fill=glow,
                  stroke_width=offset, stroke_fill=glow)
    draw.text((x1, y1), title1, font=font_main_jp, fill=TEXT_WHITE)

    # 「AI ニュースラジオ」
    title2 = "AI ニュースラジオ"
    bbox2 = draw.textbbox((0, 0), title2, font=font_sub_jp)
    tw2 = bbox2[2] - bbox2[0]
    x2 = (WIDTH - tw2) // 2
    y2 = 660
    for offset in range(6, 0, -2):
        glow = (ACCENT2[0] // 5, ACCENT2[1] // 5, ACCENT2[2] // 5)
        draw.text((x2, y2), title2, font=font_sub_jp, fill=glow,
                  stroke_width=offset, stroke_fill=glow)
    draw.text((x2, y2), title2, font=font_sub_jp, fill=ACCENT)

    # アクセントライン
    line_y = y2 + 85
    line_w = 250
    draw.line(
        [(WIDTH // 2 - line_w, line_y), (WIDTH // 2 + line_w, line_y)],
        fill=ACCENT, width=2,
    )
    for lx in [WIDTH // 2 - line_w, WIDTH // 2 + line_w]:
        draw.ellipse([(lx - 4, line_y - 4), (lx + 4, line_y + 4)], fill=ACCENT)

    # タグライン
    tagline = "毎朝 6 時配信 ─ AI が届けるテック＆経済ニュース"
    bbox_t = draw.textbbox((0, 0), tagline, font=font_tag)
    tw_t = bbox_t[2] - bbox_t[0]
    x_t = (WIDTH - tw_t) // 2
    y_t = line_y + 20
    draw.text((x_t, y_t), tagline, font=font_tag, fill=TEXT_SUB)

    # AIバッジ（右上）
    badge_text = "POWERED BY AI"
    bbox_b = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox_b[2] - bbox_b[0]
    bx = WIDTH - 80 - bw
    by = 80
    pad = 10
    draw.rounded_rectangle(
        [(bx - pad, by - pad), (bx + bw + pad, by + (bbox_b[3] - bbox_b[1]) + pad)],
        radius=8, outline=ACCENT, width=1,
    )
    draw.text((bx, by), badge_text, font=font_badge, fill=ACCENT)


def main() -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    gradient_background(draw)
    draw_dot_grid(draw)
    draw_pulse_rings(draw)
    draw_signal_bars(draw)
    draw_corner_accents(draw)
    draw_data_stream(draw)
    draw_text(draw)

    img.save(OUTPUT_PATH, "JPEG", quality=95)
    print(f"速報版カバー画像を生成しました: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
