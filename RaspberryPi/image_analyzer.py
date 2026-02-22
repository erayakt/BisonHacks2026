from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from agents.interest_factors_agent import InterestFactorsAgent
from agents.grid_scoring_agent import GridScoringAgent


class ImageAnalyzer:
    """
    Pipeline:
      1) InterestFactorsAgent.get_interest_factors(image_path) -> dict:
            {"image_context": str, "interest_factors": [ {"title":..,"description":..}, ... ]}
      2) For each factor -> GridScoringAgent.score_grid(image_path, factor)
      3) Return structured result
    """

    def __init__(
        self,
        interest_agent: Optional[InterestFactorsAgent] = None,
        grid_agent: Optional[GridScoringAgent] = None,
        *,
        continue_on_error: bool = True,
    ) -> None:
        self.interest_agent = interest_agent or InterestFactorsAgent()
        self.grid_agent = grid_agent or GridScoringAgent()
        self.continue_on_error = continue_on_error

    def analyze(self, image_path: str) -> Dict[str, Any]:
        started = time.time()

        out: Dict[str, Any] = {
            "image_path": image_path,
            "image_context": None,
            "interest_factors": [],  # list of per-factor scoring entries
            "meta": {
                "num_factors": 0,
                "duration_sec": None,
            },
            "error": None,  # fatal only
        }

        # 1) Get interest factors (DICT)
        try:
            payload = self.interest_agent.get_interest_factors(image_path)

            if not isinstance(payload, dict):
                raise TypeError(
                    f"Expected dict from get_interest_factors(), got {type(payload).__name__}"
                )

            image_context = payload.get("image_context")
            factors = payload.get("interest_factors", [])

            out["image_context"] = image_context

            if not isinstance(factors, list):
                factors = []

        except Exception as e:
            out["error"] = f"InterestFactorsAgent failed: {e}"
            out["meta"]["duration_sec"] = round(time.time() - started, 4)
            return out

        # 2) Score each factor
        for idx, factor in enumerate(factors):
            factor_obj: Dict[str, Any] = factor if isinstance(factor, dict) else {"raw": factor}

            entry: Dict[str, Any] = {
                "index": idx,
                "factor": {
                    "title": factor_obj.get("title"),
                    "description": factor_obj.get("description"),
                    "raw": factor_obj,
                },
                "grid_scoring": None,  # filled on success
                "error": None,         # per-factor error
            }

            try:
                entry["grid_scoring"] = self.grid_agent.score_grid(image_path, factor_obj)
            except Exception as e:
                entry["error"] = f"GridScoringAgent failed: {e}"
                if not self.continue_on_error:
                    out["interest_factors"].append(entry)
                    out["meta"]["num_factors"] = len(out["interest_factors"])
                    out["meta"]["duration_sec"] = round(time.time() - started, 4)
                    return out

            out["interest_factors"].append(entry)

        out["meta"]["num_factors"] = len(out["interest_factors"])
        out["meta"]["duration_sec"] = round(time.time() - started, 4)
        return out


if __name__ == "__main__":
    import json

    analyzer = ImageAnalyzer(continue_on_error=True)
    result = analyzer.analyze("../Computer/images/image3.jpg")
    print(json.dumps(result, indent=2, ensure_ascii=False))