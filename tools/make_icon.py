"""Genera ``assets/icon.ico`` (16, 24, 32, 48 y 256 px) a partir de ``favicon-20.png``.

    python tools/make_icon.py
"""

from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "assets" / "images" / "favicon-20.png"
DESTINO = RAIZ / "assets" / "icon.ico"
TAMANOS = (16, 24, 32, 48, 256)


def main() -> None:
    base = Image.open(ORIGEN).convert("RGBA")
    capas = [base.resize((t, t), Image.Resampling.LANCZOS) for t in TAMANOS]
    capas[-1].save(DESTINO, format="ICO", append_images=capas[:-1], sizes=[(t, t) for t in TAMANOS])
    print(f"Creado {DESTINO}")


if __name__ == "__main__":
    main()
