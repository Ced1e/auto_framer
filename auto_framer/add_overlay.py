"""
python add_overlay.py
                         
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

try:  # optional: lets Pillow open iPhone .heic/.heif photos
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_OK = True
except ImportError:
    HEIC_OK = False

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
if HEIC_OK:
    SUPPORTED |= {".heic", ".heif"}


def fit_overlay(overlay: Image.Image, size: tuple[int, int], mode: str) -> Image.Image:
    """Resize the overlay to match the photo size."""
    if overlay.size == size:
        return overlay

    if mode == "stretch":
        return overlay.resize(size, Image.LANCZOS)

    # "cover": scale to fill the photo, then center-crop the excess.
    # Keeps the frame's proportions (no distortion).
    ow, oh = overlay.size
    pw, ph = size
    scale = max(pw / ow, ph / oh)
    new_size = (round(ow * scale), round(oh * scale))
    resized = overlay.resize(new_size, Image.LANCZOS)
    left = (new_size[0] - pw) // 2
    top = (new_size[1] - ph) // 2
    return resized.crop((left, top, left + pw, top + ph))


def load_overlay(path: Path) -> Image.Image:
    if not path.is_file():
        sys.exit(f"Overlay not found: {path}")
    return Image.open(path).convert("RGBA")


def main() -> None:
    here = Path(__file__).resolve().parent

    p = argparse.ArgumentParser(description="Apply a frame overlay to a folder of photos.")
    p.add_argument("--input", type=Path, default=here / "input", help="folder with photos")
    p.add_argument("--output", type=Path, default=here / "output", help="folder for framed copies")
    p.add_argument("--overlay", type=Path, default=here / "overlay.png", help="overlay PNG (transparent)")
    p.add_argument("--overlay-portrait", type=Path, default=None,
                   help="optional overlay used for vertical (portrait) photos")
    p.add_argument("--fit", choices=["cover", "stretch"], default="cover",
                   help="how to fit the overlay to each photo (default: cover)")
    p.add_argument("--quality", type=int, default=95, help="JPEG quality (default: 95)")
    args = p.parse_args()

    if not args.input.is_dir():
        args.input.mkdir(parents=True)
        sys.exit(f"Created '{args.input}'. Put your photos in it and run the script again.")

    args.output.mkdir(parents=True, exist_ok=True)

    overlay = load_overlay(args.overlay)
    overlay_portrait = load_overlay(args.overlay_portrait) if args.overlay_portrait else None

    photos = sorted(f for f in args.input.iterdir() if f.suffix.lower() in SUPPORTED)
    if not photos:
        sys.exit(f"No images found in '{args.input}'.")

    ok, failed = 0, []
    for i, photo in enumerate(photos, 1):
        try:
            with Image.open(photo) as img:
                # Respect the camera's rotation flag so the photo isn't sideways.
                img = ImageOps.exif_transpose(img).convert("RGBA")

                is_portrait = img.height > img.width
                base_overlay = overlay_portrait if (is_portrait and overlay_portrait) else overlay
                frame = fit_overlay(base_overlay, img.size, args.fit)

                combined = Image.alpha_composite(img, frame)

                out_path = args.output / photo.name
                if out_path.suffix.lower() in {".heic", ".heif"}:
                    out_path = out_path.with_suffix(".jpg")  # HEIC can't be saved by Pillow; use JPG
                if out_path.suffix.lower() in {".jpg", ".jpeg"}:
                    combined.convert("RGB").save(out_path, quality=args.quality, subsampling=0)
                else:
                    combined.save(out_path)

            ok += 1
            print(f"[{i}/{len(photos)}] {photo.name}")
        except Exception as e:  # keep going if one file is bad
            failed.append((photo.name, str(e)))
            print(f"[{i}/{len(photos)}] FAILED {photo.name}: {e}")

    print(f"\nDone. {ok} framed, {len(failed)} failed. Output: {args.output}")
    for name, err in failed:
        print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()
