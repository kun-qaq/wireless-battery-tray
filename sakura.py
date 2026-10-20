"""
樱花图标绘制 (sakura)
=====================
用 PIL 程序化画一朵五瓣樱花，供托盘图标 / exe 图标 / 窗口图标使用。

花瓣颜色随「三个设备中最低的电量」变化，兼顾美观和提醒：
    > 30%   粉樱（正常）
    15~30%  枯黄（该充电了）
    <= 15%  红樱（快没电了）
    读不到   灰樱（离线）
"""
import math

from PIL import Image, ImageDraw

# 花瓣主色 / 花瓣描边色 / 花蕊色 / 花蕊深色
PALETTES = {
    "pink":  ((255, 182, 197), (243, 133, 163), (255, 214, 102), (255, 176, 60)),
    "amber": ((255, 208, 122), (238, 165, 55),  (255, 236, 170), (214, 140, 40)),
    "red":   ((240, 108, 116), (208, 62, 76),   (255, 206, 140), (190, 90, 60)),
    "gray":  ((182, 188, 196), (140, 148, 158), (222, 226, 232), (150, 156, 164)),
}

BASE_SIZE = 256          # 先画大图再缩放，小尺寸更平滑


def _petal_layer(size, petal, edge):
    """画一片花瓣：圆润的宽椭圆 + 顶端 V 形凹口（樱花的特征）。"""
    P = int(size * 0.60)
    layer = Image.new("RGBA", (P, P), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, x1 = P * 0.20, P * 0.80          # 宽椭圆，瓣形饱满
    y_top, y_bot = P * 0.04, P * 0.64
    # 外圈（略深）→ 内圈（主色），形成一点层次
    d.ellipse([x0, y_top, x1, y_bot], fill=edge + (255,))
    inset = P * 0.04
    d.ellipse([x0 + inset, y_top + inset, x1 - inset, y_bot - inset * 1.6], fill=petal + (255,))
    # 顶端凹口：用全透明三角形擦掉一块（浅口，樱花特征）
    d.polygon([(P * 0.5, P * 0.24), (x0 - P * 0.01, y_top - P * 0.03),
               (x1 + P * 0.01, y_top - P * 0.03)], fill=(0, 0, 0, 0))
    return layer


def draw_sakura(size=BASE_SIZE, palette="pink", bg=None):
    """返回一朵樱花的 RGBA 图像（size×size）。"""
    petal, edge, core, core_dark = PALETTES.get(palette, PALETTES["pink"])
    S = BASE_SIZE
    img = Image.new("RGBA", (S, S), bg or (0, 0, 0, 0))

    layer = _petal_layer(S, petal, edge)
    off = int(S / 2 - layer.width / 2)
    for i in range(5):
        # 每瓣旋转 72°；花瓣自身朝上，所以从 -90° 起算
        rot = layer.rotate(-90 + i * 72, resample=Image.BICUBIC,
                           center=(layer.width / 2, layer.height / 2))
        img.alpha_composite(rot, (off, off))

    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    r = S * 0.062
    lw = max(1, int(S * 0.016))
    # 花蕊：5 根细线 + 顶端小球
    for i in range(5):
        a = math.radians(-90 + i * 72)
        x2 = cx + math.cos(a) * r * 2.15
        y2 = cy + math.sin(a) * r * 2.15
        d.line([cx, cy, x2, y2], fill=core_dark + (255,), width=lw)
        dot = r * 0.26
        d.ellipse([x2 - dot, y2 - dot, x2 + dot, y2 + dot], fill=core_dark + (255,))
    # 花心
    d.ellipse([cx - r * 0.9, cy - r * 0.9, cx + r * 0.9, cy + r * 0.9], fill=core + (255,))
    d.ellipse([cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35],
              fill=(255, 255, 255, 235))

    if size != S:
        img = img.resize((size, size), Image.LANCZOS)
    return img


def palette_for(percents):
    """percents: [(name, val, status)] —— 按最低电量选配色。"""
    vals = [v for _, v, _ in percents if isinstance(v, int)]
    if not vals:
        return "gray"
    low = min(vals)
    if low > 30:
        return "pink"
    if low > 15:
        return "amber"
    return "red"


def make_icon(percents, size=64):
    """托盘用：按最低电量配色的樱花图标。"""
    return draw_sakura(size=size, palette=palette_for(percents))


def build_ico(path="sakura.ico"):
    """生成多尺寸 .ico，供 PyInstaller 作为 exe 图标。"""
    img = draw_sakura(BASE_SIZE, "pink")
    img.save(path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    return path


if __name__ == "__main__":
    build_ico("sakura.ico")
    for name in ("pink", "amber", "red", "gray"):
        draw_sakura(64, name).save(f"_preview_{name}.png")
    print("已生成 sakura.ico 与配色预览")
