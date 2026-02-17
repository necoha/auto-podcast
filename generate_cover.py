"""
カバー画像生成スクリプト
ダーク＆テック風 1400x1400 カバーアートを生成する
"""

import math
import random
from PIL import Image, ImageDraw, ImageFont

# --- 設定 ---
WIDTH, HEIGHT = 1400, 1400
OUTPUT_PATH = "cover.jpg"

# カラーパレット（ダーク＆テック風）
BG_TOP = (10, 10, 35)       # 濃紺（上）
BG_BOTTOM = (25, 15, 60)    # 濃紫（下）
ACCENT = (100, 140, 255)    # 青アクセント
ACCENT2 = (160, 100, 255)   # 紫アクセント
GRID_COLOR = (40, 50, 100)  # グリッド線
TEXT_WHITE = (255, 255, 255)
TEXT_SUB = (180, 190, 220)


def gradient_background(draw: ImageDraw.Draw) -> None:
    """縦グラデーション背景"""
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * ratio)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * ratio)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))


def draw_grid(draw: ImageDraw.Draw) -> None:
    """テック風の薄いグリッドパターン"""
    spacing = 70
    for x in range(0, WIDTH, spacing):
        draw.line([(x, 0), (x, HEIGHT)], fill=GRID_COLOR, width=1)
    for y in range(0, HEIGHT, spacing):
        draw.line([(0, y), (WIDTH, y)], fill=GRID_COLOR, width=1)


def draw_circuit_nodes(draw: ImageDraw.Draw) -> None:
    """回路基板風のノードとライン"""
    random.seed(42)  # 再現性のため固定シード

    nodes = []
    for _ in range(25):
        x = random.randint(50, WIDTH - 50)
        y = random.randint(50, HEIGHT - 50)
        nodes.append((x, y))

    # ノード間をラインで接続
    for i, (x1, y1) in enumerate(nodes):
        for x2, y2 in nodes[i + 1 :]:
            dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if dist < 300:
                alpha_ratio = max(0, 1 - dist / 300)
                line_color = (
                    int(ACCENT[0] * alpha_ratio * 0.3),
                    int(ACCENT[1] * alpha_ratio * 0.3),
                    int(ACCENT[2] * alpha_ratio * 0.3),
                )
                draw.line([(x1, y1), (x2, y2)], fill=line_color, width=1)

    # ノード描画（小さな光る点）
    for x, y in nodes:
        r = random.choice([3, 4, 5])
        color = random.choice([ACCENT, ACCENT2])
        # グロー効果
        for gr in range(r + 6, r, -1):
            glow = (color[0] // 4, color[1] // 4, color[2] // 4)
            draw.ellipse([(x - gr, y - gr), (x + gr, y + gr)], fill=glow)
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=color)


def draw_waveform(draw: ImageDraw.Draw, y_center: int) -> None:
    """音声波形風の装飾"""
    random.seed(99)
    bar_width = 4
    gap = 3
    total_width = 800
    start_x = (WIDTH - total_width) // 2

    for i in range(total_width // (bar_width + gap)):
        x = start_x + i * (bar_width + gap)
        # 中央が高く端が低い波形
        progress = i / (total_width // (bar_width + gap))
        envelope = math.sin(progress * math.pi) ** 0.7
        h = int(random.uniform(5, 50) * envelope + 3)

        ratio = abs(progress - 0.5) * 2
        r = int(ACCENT[0] * (1 - ratio) + ACCENT2[0] * ratio)
        g = int(ACCENT[1] * (1 - ratio) + ACCENT2[1] * ratio)
        b = int(ACCENT[2] * (1 - ratio) + ACCENT2[2] * ratio)

        draw.rectangle(
            [(x, y_center - h), (x + bar_width, y_center + h)],
            fill=(r, g, b),
        )


def draw_hexagon(draw: ImageDraw.Draw, cx: int, cy: int, radius: int, color: tuple) -> None:
    """六角形を描画"""
    points = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        px = cx + radius * math.cos(angle)
        py = cy + radius * math.sin(angle)
        points.append((px, py))
    draw.polygon(points, outline=color, fill=None)


def draw_hex_pattern(draw: ImageDraw.Draw) -> None:
    """六角形パターン装飾（上部と下部）"""
    random.seed(77)
    positions = [
        (120, 150, 45), (250, 100, 30), (1200, 120, 50), (1300, 200, 25),
        (100, 1200, 35), (200, 1300, 40), (1250, 1250, 45), (1100, 1300, 30),
    ]
    for cx, cy, r in positions:
        alpha = random.uniform(0.3, 0.7)
        color = (
            int(ACCENT[0] * alpha),
            int(ACCENT[1] * alpha),
            int(ACCENT[2] * alpha),
        )
        draw.polygon(
            [
                (cx + r * math.cos(math.radians(60 * i - 30)),
                 cy + r * math.sin(math.radians(60 * i - 30)))
                for i in range(6)
            ],
            outline=color,
        )


def draw_text(draw: ImageDraw.Draw) -> None:
    """メインテキスト描画"""
    # フォント（英語: Helvetica Bold, 日本語: ヒラギノ角ゴシック）
    FONT_EN = "/System/Library/Fonts/Helvetica.ttc"
    FONT_JP = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
    try:
        font_title = ImageFont.truetype(FONT_EN, 120)
        font_sub = ImageFont.truetype(FONT_EN, 48)
        font_tag = ImageFont.truetype(FONT_JP, 36)
    except (OSError, IOError):
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_tag = ImageFont.load_default()

    # メインタイトル "AI AUTO"
    title1 = "AI AUTO"
    bbox1 = draw.textbbox((0, 0), title1, font=font_title)
    tw1 = bbox1[2] - bbox1[0]
    x1 = (WIDTH - tw1) // 2
    y1 = 480

    # グロー効果
    for offset in range(8, 0, -2):
        glow_color = (ACCENT[0] // 6, ACCENT[1] // 6, ACCENT[2] // 6)
        draw.text((x1, y1), title1, font=font_title, fill=glow_color,
                  stroke_width=offset, stroke_fill=glow_color)
    draw.text((x1, y1), title1, font=font_title, fill=TEXT_WHITE)

    # メインタイトル "PODCAST"
    title2 = "PODCAST"
    bbox2 = draw.textbbox((0, 0), title2, font=font_title)
    tw2 = bbox2[2] - bbox2[0]
    x2 = (WIDTH - tw2) // 2
    y2 = 600
    for offset in range(8, 0, -2):
        glow_color = (ACCENT2[0] // 6, ACCENT2[1] // 6, ACCENT2[2] // 6)
        draw.text((x2, y2), title2, font=font_title, fill=glow_color,
                  stroke_width=offset, stroke_fill=glow_color)
    draw.text((x2, y2), title2, font=font_title, fill=TEXT_WHITE)

    # アクセントライン
    line_y = y2 + 140
    line_w = 300
    draw.line(
        [(WIDTH // 2 - line_w, line_y), (WIDTH // 2 + line_w, line_y)],
        fill=ACCENT, width=3,
    )
    # 両端に小さな円
    for lx in [WIDTH // 2 - line_w, WIDTH // 2 + line_w]:
        draw.ellipse([(lx - 5, line_y - 5), (lx + 5, line_y + 5)], fill=ACCENT)

    # サブタイトル
    subtitle = "TECH & ECONOMY NEWS"
    bbox_s = draw.textbbox((0, 0), subtitle, font=font_sub)
    tw_s = bbox_s[2] - bbox_s[0]
    x_s = (WIDTH - tw_s) // 2
    y_s = line_y + 25
    draw.text((x_s, y_s), subtitle, font=font_sub, fill=TEXT_SUB)

    # タグライン
    tagline = "AI が届ける毎朝のテック＆経済ニュース"
    bbox_t = draw.textbbox((0, 0), tagline, font=font_tag)
    tw_t = bbox_t[2] - bbox_t[0]
    x_t = (WIDTH - tw_t) // 2
    y_t = y_s + 70
    draw.text((x_t, y_t), tagline, font=font_tag, fill=TEXT_SUB)


def main() -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)

    # 1. グラデーション背景
    gradient_background(draw)

    # 2. グリッドパターン
    draw_grid(draw)

    # 3. 回路ノード
    draw_circuit_nodes(draw)

    # 4. 六角形装飾
    draw_hex_pattern(draw)

    # 5. 波形装飾（テキストの上下）
    draw_waveform(draw, y_center=400)
    draw_waveform(draw, y_center=1000)

    # 6. テキスト
    draw_text(draw)

    # 保存
    img.save(OUTPUT_PATH, "JPEG", quality=95)
    print(f"カバー画像を生成しました: {OUTPUT_PATH} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
