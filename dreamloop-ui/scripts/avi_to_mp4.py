"""Convert AVI to browser-ready H.264 MP4. Requires: pip install imageio-ffmpeg"""
import subprocess
import sys
from pathlib import Path

try:
    import imageio_ffmpeg
except ImportError:
    raise SystemExit("Install: pip install imageio-ffmpeg")


def convert(avi_path: Path, mp4_path: Path | None = None) -> Path:
    mp4_path = mp4_path or avi_path.with_suffix(".mp4")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(avi_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            str(mp4_path),
        ],
        check=True,
    )
    print(f"Wrote {mp4_path} ({mp4_path.stat().st_size} bytes)")
    return mp4_path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "public" / "videos"
    paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else list(root.glob("*.avi"))
    if not paths:
        raise SystemExit("No .avi files found. Usage: python scripts/avi_to_mp4.py [file.avi ...]")
    for avi in paths:
        convert(avi)
