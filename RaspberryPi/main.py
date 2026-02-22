from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from config import IMAGE_CONFIG, MOUSE_CONFIG, WS_CONFIG
from image_analyzer import ImageAnalyzer
from inputs.mouse_input import MouseInput
from network.ws_client import WebSocketClient, WebSocketClientConfig
from outputs.audio_output import LoopingWavOutput
from outputs.tone_output import ToneOutput  # fallback if WAV backend fails


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("main")


ROWS = 6
COLS = 6
COL_LABELS = ["A", "B", "C", "D", "E", "F"]


def _cache_path_for_image(image_path: str, cache_dir: str) -> Path:
    p = Path(image_path)
    stem = p.name  # keep extension in name to avoid collisions (user asked "name it with image file name")
    # Ensure .json suffix
    return Path(cache_dir) / f"{stem}.json"


def load_or_run_image_analysis(image_path: str, *, cache_dir: str, force: bool = False) -> Dict[str, Any]:
    """
    Run the image->grid pipeline once at startup.
    - If cache exists: load it and skip AI calls.
    - Else: run ImageAnalyzer and store JSON cache.

    Cache file name is based on the image file name (including extension), as requested.
    """
    cache_path = _cache_path_for_image(image_path, cache_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if (not force) and cache_path.exists():
        logger.info("Loading cached analysis: %s", cache_path)
        return json.loads(cache_path.read_text(encoding="utf-8"))

    logger.info("Running image analysis (no cache yet): %s", image_path)
    analyzer = ImageAnalyzer(continue_on_error=True)
    result = analyzer.analyze(image_path)

    cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved cache: %s", cache_path)
    return result


def pick_grid_map(result: Dict[str, Any], factor_index: int) -> Optional[Dict[str, int]]:
    """
    Extract a {"A1":..,"F6":..} map from ImageAnalyzer output for the chosen factor.
    """
    factors = result.get("interest_factors") or []
    if not isinstance(factors, list) or not factors:
        return None

    # Try requested index first, then fallback to first valid map
    indices = [factor_index] + [i for i in range(len(factors)) if i != factor_index]
    for idx in indices:
        if idx < 0 or idx >= len(factors):
            continue
        entry = factors[idx]
        if not isinstance(entry, dict):
            continue
        scoring = entry.get("grid_scoring")
        if isinstance(scoring, dict):
            grid_map = scoring.get("grid_map")
            if isinstance(grid_map, dict) and grid_map:
                # sanitize to int 0..100
                out: Dict[str, int] = {}
                for k, v in grid_map.items():
                    try:
                        iv = int(v)
                    except Exception:
                        iv = 0
                    if iv < 0:
                        iv = 0
                    if iv > 100:
                        iv = 100
                    out[str(k)] = iv
                # Ensure all 36 keys exist
                for r in range(1, ROWS + 1):
                    for c in COL_LABELS:
                        out.setdefault(f"{c}{r}", 0)
                return out
    return None


def cell_from_xy(x: int, y: int, *, w: int, h: int) -> Tuple[str, int, int]:
    """
    Map absolute (x,y) in [0..w]x[0..h] into a 6x6 cell label and indices.
    Returns (label, row_idx, col_idx) where row_idx/col_idx are 0-based.
    """
    # avoid division by zero
    w = max(1, int(w))
    h = max(1, int(h))

    col = int((x / w) * COLS)
    row = int((y / h) * ROWS)

    # clamp
    col = max(0, min(COLS - 1, col))
    row = max(0, min(ROWS - 1, row))

    label = f"{COL_LABELS[col]}{row + 1}"
    return label, row, col


async def run() -> None:
    # ---------------------------
    # 0) Image processing pipeline at startup (with JSON cache)
    # ---------------------------
    image_path = os.getenv("IMAGE_PATH", IMAGE_CONFIG.image_path)
    cache_dir = os.getenv("CACHE_DIR", IMAGE_CONFIG.cache_dir)
    factor_index = int(os.getenv("FACTOR_INDEX", str(IMAGE_CONFIG.factor_index)))

    analysis = load_or_run_image_analysis(image_path, cache_dir=cache_dir, force=False)
    grid_map = pick_grid_map(analysis, factor_index=factor_index)

    if not grid_map:
        logger.warning("No grid_map found in analysis result. Audio feedback will be silent.")
        grid_map = {f"{c}{r}": 0 for r in range(1, ROWS + 1) for c in COL_LABELS}

    # Audio feedback: loop a WAV file and adjust intensity based on cell score
    _audio_backend = "wav"
    player: Optional[LoopingWavOutput] = None
    tone: Optional[ToneOutput] = None

    wav_path = os.getenv("SOUND_FILE", IMAGE_CONFIG.sound_file_path)
    min_intensity = float(os.getenv("MIN_INTENSITY", str(IMAGE_CONFIG.min_intensity)))
    intensity_factor = float(os.getenv("INTENSITY_FACTOR", str(IMAGE_CONFIG.intensity_factor)))

    def _debug_gain(level_int: int) -> float:
        # Mirror LoopingWavOutput.set_level mapping for debugging
        lv = float(level_int)
        if lv < 0.0:
            lv = 0.0
        if lv > 100.0:
            lv = 100.0
        raw = lv / 100.0
        mi = min(max(min_intensity, 0.0), 1.0)
        fac = max(intensity_factor, 0.0)
        gain = mi + raw * fac
        if gain < 0.0:
            gain = 0.0
        if gain > 1.0:
            gain = 1.0
        return float(gain)


    try:
        player = LoopingWavOutput()
        player.start(wav_path)
        player.set_level(0, min_intensity=min_intensity, intensity_factor=intensity_factor)
        _audio_backend = "wav"
        logger.info("Audio backend: WAV loop (%s)", wav_path)
    except Exception as e:
        logger.warning("WAV backend failed (%s). Falling back to sine tone.", e)
        tone = ToneOutput()
        tone.start(freq_hz=float(os.getenv("TONE_FREQ_HZ", "440.0")), level=0)
        _audio_backend = "tone"
        logger.info("Audio backend: sine tone")

    # ---------------------------
    # 1) Normal runtime: mouse + websocket + audio feedback
    # ---------------------------
    mouse = MouseInput(MOUSE_CONFIG)
    mouse.start()

    ws = WebSocketClient(
        WebSocketClientConfig(
            server_uri=WS_CONFIG.server_uri,
            reconnect_delay_s=WS_CONFIG.reconnect_delay_s,
        )
    )
    ws.start()

    ws.send_json({"type": "hello", "device": "raspberrypi", "ts": time.time()})

    last_cell: Optional[str] = None
    last_level: Optional[int] = None

    try:
        last_sent = 0.0
        min_interval_s = 1.0 / 60.0  # cap to 60Hz

        while True:
            now = time.time()

            moved = mouse.is_moved()
            if moved and (now - last_sent) >= min_interval_s:
                x, y = mouse.get_absolute_position()

                # 1) Send position to computer
                ws.send_json(
                    {
                        "type": "mouse_pos",
                        "x": x,
                        "y": y,
                        "w": MOUSE_CONFIG.max_x,
                        "h": MOUSE_CONFIG.max_y,
                        "ts": now,
                    }
                )
                last_sent = now

                # 2) Local audio feedback based on current cell score (0..100)
                cell, _, _ = cell_from_xy(x, y, w=MOUSE_CONFIG.max_x, h=MOUSE_CONFIG.max_y)
                level = int(grid_map.get(cell, 0))

                # Update audio only if something changed
                if cell != last_cell or level != last_level:
                    gain_dbg = _debug_gain(level)
                    print(f"[CELL] {cell} -> score={level} gain={gain_dbg:.3f} (min={min_intensity:.3f} factor={intensity_factor:.3f})")
                    if _audio_backend == "wav" and player is not None:
                        player.set_level(level, min_intensity=min_intensity, intensity_factor=intensity_factor)
                    elif _audio_backend == "tone" and tone is not None:
                        tone.set_level(level)
                    last_cell = cell
                    last_level = level
            # If not moved: keep last intensity (do not go quiet)

            await asyncio.sleep(0.005)

    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if _audio_backend == "wav" and player is not None:
                player.set_level(0, min_intensity=min_intensity, intensity_factor=intensity_factor)
                player.stop()
            elif _audio_backend == "tone" and tone is not None:
                tone.set_level(0)
                tone.stop()
        except Exception:
            pass
        try:
            ws.stop()
        except Exception:
            pass
        try:
            mouse.stop()
        except Exception:
            pass


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
