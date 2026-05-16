from pathlib import Path

import cairosvg

SVG_SOURCE = Path("src/static/icon.svg")
SIZES = {
    "favicon-16.png": 16,
    "favicon-32.png": 32,
    "apple-touch-icon.png": 180,
    "icon-192.png": 192,
    "icon-512.png": 512,
}


def main() -> None:
    if not SVG_SOURCE.exists():
        raise FileNotFoundError(f"SVG source not found: {SVG_SOURCE}")

    output_dir = Path("src/static/icons")
    output_dir.mkdir(parents=True, exist_ok=True)

    for file_name, px in SIZES.items():
        cairosvg.svg2png(
            url=str(SVG_SOURCE),
            write_to=str(output_dir / file_name),
            output_width=px,
            output_height=px,
        )


if __name__ == "__main__":
    main()
