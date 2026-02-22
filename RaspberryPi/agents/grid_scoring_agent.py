import json
import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
from agents.image_agent import ImageAgent


class GridScoringAgent(ImageAgent):
    """
    Overlays a 6x6 coordinate grid (A1..F6) on an image and scores each cell
    based on a specified visual interest factor.

    Robustness goals:
    - Accepts LLM output as either:
        1) {"grid_values": {"A1": 10, ...}}
        2) {"A1": 10, "A2": 5, ...}   (flat dict)
    - Handles code fences (```json ... ```)
    - Extracts JSON from mixed text safely
    - Validates/clamps values to int [0, 100] and always returns all 36 cells

    Output:
    - Returns BOTH:
        - cleaned_map: {"A1": int, ..., "F6": int}
        - matrix: 6x6 list (rows 1..6, cols A..F)
    """

    ROWS = 6
    COLS = 6
    COL_LABELS = ["A", "B", "C", "D", "E", "F"]

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash-lite",
        default_prompt: Optional[str] = None,
    ):
        json_instruction = (
            "You are an expert visual accessibility AI designed to map images to tactile/audio feedback grids. "
            "The user will provide an image that has a 6x6 coordinate grid (A1 to F6) visually overlaid on it. "
            "You will also be given a specific 'Interest Factor' to look for.\n\n"
            "Your task is to evaluate EVERY single cell in the 6x6 grid and assign it a score from 0 to 100 based "
            "on the intensity, density, or presence of the specified Interest Factor in that cell.\n"
            "- 0 means the factor is entirely absent or at its lowest possible intensity.\n"
            "- 100 means the factor is at its absolute maximum intensity.\n\n"
            "Return ONLY valid JSON. Do not include markdown or extra text.\n"
            "You MUST return exactly one of these schemas:\n\n"
            "Schema A (preferred):\n"
            '{ "grid_values": { "A1": 0, "A2": 10, ..., "F6": 45 } }\n\n'
            "Schema B (also accepted):\n"
            '{ "A1": 0, "A2": 10, ..., "F6": 45 }\n'
        )
        super().__init__(
            model_name=model_name,
            default_prompt=default_prompt or json_instruction,
        )

    # --------------------------- Grid drawing ---------------------------

    def _draw_grid_with_labels(self, image_path: str) -> str:
        """Loads image, draws 6x6 grid + centered labels (A1..F6), saves to a temp file."""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Could not load image at {image_path}")

        h, w, _ = img.shape
        dy, dx = h / self.ROWS, w / self.COLS

        # Grid visual styling
        grid_color = (0, 255, 0)  # neon green
        thickness = max(1, int(min(h, w) * 0.003))

        # Draw vertical lines
        for x in range(1, self.COLS):
            x_pos = int(round(x * dx))
            cv2.line(img, (x_pos, 0), (x_pos, h), grid_color, thickness)

        # Draw horizontal lines
        for y in range(1, self.ROWS):
            y_pos = int(round(y * dy))
            cv2.line(img, (0, y_pos), (w, y_pos), grid_color, thickness)

        # Draw Labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = min(dx, dy) * 0.012
        font_thickness = max(1, int(font_scale * 2))

        for r in range(self.ROWS):
            for c in range(self.COLS):
                label = f"{self.COL_LABELS[c]}{r + 1}"

                text_size = cv2.getTextSize(label, font, font_scale, font_thickness)[0]
                cell_x_start = int(c * dx)
                cell_y_start = int(r * dy)
                text_x = cell_x_start + int((dx - text_size[0]) / 2)
                text_y = cell_y_start + int((dy + text_size[1]) / 2)

                # black outline for readability
                cv2.putText(
                    img,
                    label,
                    (text_x, text_y),
                    font,
                    font_scale,
                    (0, 0, 0),
                    font_thickness + 2,
                    cv2.LINE_AA,
                )
                # magenta label
                cv2.putText(
                    img,
                    label,
                    (text_x, text_y),
                    font,
                    font_scale,
                    (255, 0, 255),
                    font_thickness,
                    cv2.LINE_AA,
                )

        fd, temp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        ok = cv2.imwrite(temp_path, img)
        if not ok:
            raise RuntimeError("Failed to write temporary grid image.")
        return temp_path

    # --------------------------- Public API ---------------------------

    def score_grid(
        self,
        image_path: str,
        factor: Dict[str, str],
        custom_prompt: Optional[str] = None,
        return_format: str = "both",  # "matrix" | "map" | "both"
    ) -> Union[List[List[int]], Dict[str, int], Dict[str, Any]]:
        """
        Overlays grid, queries LLM, parses/validates output, and returns:
          - "matrix": 6x6 list of ints (rows 1..6, cols A..F)
          - "map": {"A1": int, ..., "F6": int}
          - "both": {"grid_map": {...}, "grid_matrix": [[...],[...],...]}
        """
        temp_img_path = self._draw_grid_with_labels(image_path)

        factor_title = factor.get("title", "Unknown Factor")
        factor_desc = factor.get("description", "No description provided.")

        task_prompt = (
            f"Analyze the attached image based strictly on this Interest Factor:\n"
            f"TITLE: {factor_title}\n"
            f"DESCRIPTION: {factor_desc}\n\n"
            "Look at the visual 6x6 grid overlaid on the image. Assign a score from 0 to 100 for each cell "
            "(A1 through F6) based on this factor.\n"
            "Return ONLY valid JSON, no markdown and no commentary.\n"
            'Use schema: { "grid_values": { "A1": 0, ..., "F6": 0 } } '
            "or a flat dict { \"A1\": 0, ..., \"F6\": 0 }."
        )

        final_prompt = custom_prompt or task_prompt

        try:
            text = self.analyze_image(temp_img_path, custom_prompt=final_prompt)

            if isinstance(text, str) and text.startswith("Error:"):
                raise RuntimeError(text)

            raw_obj = self._safe_json_parse(text)
            grid_map_raw = self._extract_grid_map(raw_obj)
            grid_map = self._validate_and_fill_grid(grid_map_raw)
            grid_matrix = self._map_to_matrix(grid_map)

            if return_format == "matrix":
                return grid_matrix
            if return_format == "map":
                return grid_map
            return {"grid_map": grid_map, "grid_matrix": grid_matrix}

        finally:
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)

    # --------------------------- Conversions ---------------------------

    @classmethod
    def _map_to_matrix(cls, grid_map: Dict[str, int]) -> List[List[int]]:
        """
        Convert {"A1":..,"F6":..} -> 6x6 matrix:
          - row 0 is row 1 (A1..F1)
          - row 5 is row 6 (A6..F6)
        """
        matrix: List[List[int]] = []
        for r in range(1, cls.ROWS + 1):
            row_vals = []
            for c in cls.COL_LABELS:
                row_vals.append(int(grid_map.get(f"{c}{r}", 0)))
            matrix.append(row_vals)
        return matrix

    @classmethod
    def _matrix_to_map(cls, matrix: List[List[Any]]) -> Dict[str, int]:
        """
        Convert 6x6 matrix -> {"A1":..,"F6":..}.
        If matrix shape is wrong, missing values default to 0.
        """
        out: Dict[str, int] = {}
        for r in range(1, cls.ROWS + 1):
            for c_idx, c in enumerate(cls.COL_LABELS):
                v = 0
                try:
                    v = matrix[r - 1][c_idx]
                except Exception:
                    v = 0
                out[f"{c}{r}"] = cls._coerce_score(v)
        return out

    # --------------------------- Parsing + Validation ---------------------------

    @staticmethod
    def _strip_code_fences(s: str) -> str:
        s = s.strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            return fence_match.group(1).strip()
        return s

    @classmethod
    def _safe_json_parse(cls, text: Any) -> Dict[str, Any]:
        """Robust JSON extraction from LLM output. Returns dict if possible; otherwise {}."""
        if not isinstance(text, str):
            return {}

        cleaned = cls._strip_code_fences(text)

        # Attempt direct json parse
        try:
            obj = json.loads(cleaned)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass

        # Fallback: extract the outermost {...} region and parse it
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start : end + 1]
            try:
                obj = json.loads(candidate)
                return obj if isinstance(obj, dict) else {}
            except Exception:
                return {}

        return {}

    @classmethod
    def _extract_grid_map(cls, obj: Dict[str, Any]) -> Dict[str, Any]:
        """
        Accepts either:
          - {"grid_values": {...}}
          - {"A1": 10, ...} (flat)
        Returns best guess mapping of cell->value (possibly empty).
        """
        if not isinstance(obj, dict):
            return {}

        gv = obj.get("grid_values")
        if isinstance(gv, dict):
            return gv

        valid_keys = cls._valid_cell_keys_set()
        hits = sum(1 for k in obj.keys() if isinstance(k, str) and k.strip().upper() in valid_keys)
        if hits >= 6:  # heuristic threshold
            return obj

        for alt in ("values", "cells", "grid", "scores"):
            alt_map = obj.get(alt)
            if isinstance(alt_map, dict):
                return alt_map

        return {}

    @classmethod
    def _valid_cell_keys_set(cls) -> set:
        return {f"{c}{r}" for r in range(1, cls.ROWS + 1) for c in cls.COL_LABELS}

    @classmethod
    def _coerce_score(cls, v: Any) -> int:
        """Coerce value into an int in [0, 100]. Handles ints/floats/numeric strings and messy strings."""
        if v is None:
            return 0

        if isinstance(v, (int, float)):
            return int(max(0, min(100, round(v))))

        if isinstance(v, str):
            s = v.strip()
            m = re.search(r"-?\d+(\.\d+)?", s)
            if not m:
                return 0
            try:
                num = float(m.group(0))
                return int(max(0, min(100, round(num))))
            except Exception:
                return 0

        return 0

    @classmethod
    def _validate_and_fill_grid(cls, grid_values: Dict[str, Any]) -> Dict[str, int]:
        """Return exactly 36 keys A1..F6, ints 0..100. Missing/invalid -> 0."""
        cleaned: Dict[str, int] = {}
        valid_keys = cls._valid_cell_keys_set()

        normalized: Dict[str, Any] = {}
        if isinstance(grid_values, dict):
            for k, v in grid_values.items():
                if not isinstance(k, str):
                    continue
                kk = k.strip().upper()
                if kk in valid_keys:
                    normalized[kk] = v

        for r in range(1, cls.ROWS + 1):
            for c in cls.COL_LABELS:
                key = f"{c}{r}"
                cleaned[key] = cls._coerce_score(normalized.get(key, 0))

        return cleaned


# --- Usage Example ---
if __name__ == "__main__":
    scorer = GridScoringAgent()

    sample_factor = {
        "title": "Land Elevation Intensity",
        "description": (
            "Represents the physical height above sea level, indicated by color gradients. "
            "Low intensity corresponds to sea level or lowlands (green areas), while high intensity "
            "corresponds to mountains (brown and dark yellow areas). This variation can control resistance."
        ),
    }

    try:
        result = scorer.score_grid(
            "../Computer/images/image2.jpg",
            sample_factor,
            return_format="both",  # "matrix" | "map" | "both"
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Failed: {e}")