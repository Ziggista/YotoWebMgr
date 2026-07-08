from pathlib import Path


def pixelise_artwork(
    *,
    source_path: str,
    output_path: str,
    size: int = 16,
    colors: int = 16,
) -> tuple[int, int]:
    from PIL import Image

    source = Path(source_path)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        image = image.convert("RGB")
        width, height = image.size
        crop_size = min(width, height)
        left = (width - crop_size) // 2
        top = (height - crop_size) // 2
        image = image.crop((left, top, left + crop_size, top + crop_size))
        resampling = getattr(Image.Resampling, "NEAREST", Image.NEAREST)
        image = image.resize((size, size), resampling)
        dither = getattr(Image.Dither, "NONE", Image.NONE)
        palette = getattr(Image.Palette, "ADAPTIVE", Image.ADAPTIVE)
        image = image.convert("P", palette=palette, colors=colors, dither=dither)
        image.save(destination, format="PNG", optimize=False)

    return size, size
