import argparse
import io
import os
from pathlib import Path
from typing import Literal, cast

_ = os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

import cairosvg  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image, ImageFilter
from psd_tools import PSDImage

ROOT = Path(__file__).parent
IN_DIR = ROOT / "in"
OUT_DIR = ROOT / "out"

def pngify_svg(svg_path: Path, mark_width: int) -> Image.Image:
    png = cast(bytes, cairosvg.svg2png(url=str(svg_path), output_width=mark_width))  # pyright: ignore[reportUnknownMemberType]
    return Image.open(io.BytesIO(png)).convert("RGBA")

type Corner = Literal["top-left", "top-right", "bottom-left", "bottom-right"]


def apply_watermark(
    img: Image.Image,
    mark: Image.Image,
    corner: Corner = "bottom-right",
    margin: int = 0,
    width: int | None = None,
) -> Image.Image:
    """Paste `mark` into a corner of `img`, `margin` px from the edges.

    If `width` is given, `mark` is resized to that width, keeping its aspect ratio.
    """
    if width is not None:
        height = round(mark.height * width / mark.width)
        mark = mark.resize((width, height), Image.Resampling.LANCZOS)

    x = margin if corner.endswith("left") else img.width - mark.width - margin
    y = margin if corner.startswith("top") else img.height - mark.height - margin

    out = img.copy()
    out.paste(mark, (x, y), mark)
    return out


def make_thumbnail(img: Image.Image, max_size: int) -> Image.Image:
    thumb = img.copy()
    thumb.thumbnail((max_size, max_size))
    return thumb

def convert_psd_to_jpg(file_path: Path, out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    """Write `<stem>.jpg` (watermarked) and `<stem>_thumb.jpg` to `out_dir`, returning both paths."""
    psdimage = PSDImage.open(file_path)
    image = psdimage.composite()

    image = image.convert('RGB').filter(ImageFilter.SHARPEN)
    thumbnail = make_thumbnail(image, 400)
    margin = 80  # padding of watermarks from the image edges
    main = make_thumbnail(image, 2000)  # since image is only shrinking, can reuse
    stamp = pngify_svg(IN_DIR / 'stamp.svg', 100)  # create png watermark with [int] width
    link = Image.open(IN_DIR / 'link.png').convert('RGBA')

    main = apply_watermark(main, stamp, "top-left", margin)
    main = apply_watermark(main, link, margin=20, width=250)

    out_dir.mkdir(parents=True, exist_ok=True)
    main_path = out_dir / f'{file_path.stem}.jpg'
    thumb_path = out_dir / f'{file_path.stem}_thumb.jpg'
    main.save(main_path)
    thumbnail.save(thumb_path)
    return main_path, thumb_path

def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PSDs to watermarked JPGs in out/.")
    _ = parser.add_argument("psd", type=Path, nargs="+", help="PSD file(s) to convert")
    args = parser.parse_args()

    psd_paths = cast(list[Path], args.psd)
    for psd_path in psd_paths:
        if not psd_path.is_file():
            parser.error(f"file not found: {psd_path}")
    for psd_path in psd_paths:
        main_path, _ = convert_psd_to_jpg(psd_path)
        print(f"{psd_path} -> {main_path}")

if __name__ == "__main__":
    main()
