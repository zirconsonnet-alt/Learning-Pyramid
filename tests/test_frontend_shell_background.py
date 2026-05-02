from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_CSS = REPO_ROOT / "frontend" / "src" / "index.css"


def test_shell_glow_fades_before_its_fixed_layer_is_clipped() -> None:
    source = INDEX_CSS.read_text(encoding="utf-8")
    block_start = source.index(".theme-shell-glow")
    block_end = source.index("}", block_start)
    shell_glow_block = source[block_start:block_end]

    assert "mask-image: linear-gradient(180deg" in shell_glow_block
    assert "-webkit-mask-image: linear-gradient(180deg" in shell_glow_block
