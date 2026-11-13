from PIL import Image, ImageDraw

def icon(size, pad):
    im = Image.new("RGBA", (size, size), (20, 67, 46, 255))
    d = ImageDraw.Draw(im)
    c = size / 2
    r = size * (0.5 - pad)
    d.ellipse([c - r, c - r, c + r, c + r], fill=(247, 244, 236, 255))
    w = max(2, int(size * 0.075))
    pts = [(c - r * 0.48, c + r * 0.02), (c - r * 0.12, c + r * 0.38), (c + r * 0.52, c - r * 0.34)]
    d.line(pts, fill=(20, 67, 46, 255), width=w, joint="curve")
    for p in (pts[0], pts[2]):
        d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=(20, 67, 46, 255))
    return im

icon(192, 0.12).save("frontend/icon-192.png")
icon(512, 0.12).save("frontend/icon-512.png")
icon(512, 0.22).save("frontend/icon-maskable-512.png")
print("icons created")