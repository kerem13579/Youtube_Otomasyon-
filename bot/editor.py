"""ffmpeg post: normalise to 9:16 Shorts, upscale, burn the subscribe bumper.

The chromakey settings here were measured against the supplied bumper:
its green is exactly 0x01FC00. `colorkey` leaves a yellow-green rim around
the badge; `chromakey` + `despill` at similarity 0.16 is clean.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import ASSETS, WORK

GREEN = "0x01FC00"
SIMILARITY = "0.16"
BLEND = "0.08"

# Where the bumper sits in the frame, as a fraction of height. 0.72 keeps it
# clear of the Shorts UI at the bottom and out of the action in the middle.
BUMPER_Y = 0.72
BUMPER_WIDTH_FRAC = 0.80


def run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = proc.stderr.strip().splitlines()[-12:]
        raise RuntimeError("ffmpeg failed:\n" + "\n".join(tail))


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "duration": float(info["format"]["duration"]),
        "has_audio": has_audio,
    }


def finish(source: Path, dest: Path, *, bumper: Path | None = None,
           bumper_start: float = 3.0, target_w: int = 1080,
           target_h: int = 1920) -> Path:
    """Upscale to 1080x1920, denoise/sharpen, and overlay the bumper."""
    bumper = bumper or (ASSETS / "subscribe_overlay.mp4")
    info = probe(source)
    dest.parent.mkdir(parents=True, exist_ok=True)

    bumper_w = int(target_w * BUMPER_WIDTH_FRAC)
    if bumper_w % 2:
        bumper_w -= 1

    bumper_info = probe(bumper)
    bumper_end = bumper_start + bumper_info["duration"]
    if bumper_end > info["duration"] - 1.0:
        # Never let the bumper run into the reveal; slide it earlier instead.
        bumper_start = max(1.0, info["duration"] - 1.0 - bumper_info["duration"])
        bumper_end = bumper_start + bumper_info["duration"]

    # The generated clip is already 9:16; scale+pad guards against a model
    # that quietly returns a different ratio.
    base_chain = (
        f"hqdn3d=1.5:1.5:6:6,"
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"unsharp=5:5:0.45:5:5:0.0,setsar=1"
    )
    overlay_chain = (
        f"[1:v]scale={bumper_w}:-2,"
        f"chromakey={GREEN}:{SIMILARITY}:{BLEND},despill,"
        f"setpts=PTS-STARTPTS+{bumper_start}/TB[ck]"
    )
    filter_complex = (
        f"[0:v]{base_chain}[base];"
        f"{overlay_chain};"
        f"[base][ck]overlay=x=(W-w)/2:y=H*{BUMPER_Y}:"
        f"enable='between(t,{bumper_start:.2f},{bumper_end:.2f})':shortest=0[v]"
    )

    args = ["ffmpeg", "-y", "-i", str(source), "-i", str(bumper),
            "-filter_complex", filter_complex, "-map", "[v]"]
    if info["has_audio"]:
        # The bumper's own audio is dropped on purpose - this format is silent
        # apart from the build's diegetic sound.
        args += ["-map", "0:a", "-c:a", "aac", "-b:a", "192k"]
    args += ["-c:v", "libx264", "-preset", "slow", "-crf", "19",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest)]
    run(args)
    return dest


def audio_is_silent(path: Path, threshold_db: float = -60.0) -> bool:
    """A silent render wastes the whole generation - catch it before upload."""
    proc = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "mean_volume:" in line:
            try:
                return float(line.split("mean_volume:")[1].split("dB")[0]) < threshold_db
            except (IndexError, ValueError):
                return False
    return True  # no audio stream at all


def workdir() -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    return WORK
