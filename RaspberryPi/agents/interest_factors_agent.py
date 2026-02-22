import json
from typing import Any, Dict, List, Optional

from agents.image_agent import ImageAgent

class InterestFactorsAgent(ImageAgent):
    """
    An agent specialized to extract 'interest factors' and image context 
    for a tactile/audio feedback accessibility device.

    - Inherits from ImageAgent
    - Returns a strict JSON structure containing the image context and singular, quantifiable factors.
    - Uses an advanced prompt with strict rules and few-shot examples.
    """

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash-lite",
        default_prompt: Optional[str] = None,
    ):
        json_instruction = (
            "You are an expert visual accessibility AI analyzing an image for a hardware feedback device. "
            "A visually impaired user explores this image using a mouse-like device that provides tactile "
            "(e.g., vibration, resistance) or auditory (e.g., tone pitch) feedback based on image properties.\n\n"
            "Your task is to identify the overall context of the image and extract a list of 1 to 6 "
            "highly quantifiable, continuous visual factors that vary across the image.\n\n"
            "=== RULES ===\n"
            "1. MAXIMUM 6 FACTORS: Do not output more than 6 items in the list.\n"
            "2. CONTINUOUS OVER DISCRETE: Prioritize gradients, intensities, and densities (e.g., brightness, texture roughness, color saturation) over simple object counts.\n"
            "3. STRICTLY SINGULAR: Never combine concepts. 'Redness' is good; 'Color and Size' is a violation.\n"
            "4. TITLE LENGTH: The 'title' MUST be exactly 3 to 4 words. No exceptions.\n"
            "5. NO SPATIAL DATA: Do not describe *where* things are (e.g., 'top left'). Only describe the factor itself.\n"
            "6. HARDWARE-READY DESCRIPTIONS: The 'description' is for a downstream AI. It must explain how the factor's intensity varies so the AI can map it to a parameter range (e.g., 'Values range from low (smooth areas) to high (detailed areas)').\n\n"
            "=== OUTPUT SCHEMA ===\n"
            "Return ONLY valid JSON. No markdown formatting or extra text.\n"
            "{\n"
            '  "image_context": string, // Briefly describe the image type (e.g., "Topographic Map", "Circuit Board Schematic", "Portrait Photography")\n'
            '  "interest_factors": [\n'
            '    {\n'
            '      "title": string, // Exactly 3-4 words.\n'
            '      "description": string // How it manifests and varies for hardware mapping.\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            "=== EXAMPLES ===\n"
            "Example 1 (Topographic Map):\n"
            "{\n"
            '  "image_context": "Topographic Map of a Mountainous Region",\n'
            '  "interest_factors": [\n'
            '    {\n'
            '      "title": "Terrain Elevation Gradient",\n'
            '      "description": "Represents the physical height of the terrain. Low intensity corresponds to sea level or valleys (darker/flatter regions), while high intensity corresponds to mountain peaks (dense contour lines or lighter colors). Use to map varying resistance."\n'
            '    },\n'
            '    {\n'
            '      "title": "Vegetation Density Level",\n'
            '      "description": "Represents the concentration of plant life, indicated by the saturation of green hues. Low intensity indicates barren rock or snow, while high intensity indicates dense forest. Suitable for mapping to vibration frequency."\n'
            '    }\n'
            '  ]\n'
            "}\n\n"
            "Example 2 (Circuit Board Schematic):\n"
            "{\n"
            '  "image_context": "Electronic Circuit Board Schematic",\n'
            '  "interest_factors": [\n'
            '    {\n'
            '      "title": "Circuit Trace Density",\n'
            '      "description": "Measures the concentration of copper traces in a given area. Empty fiberglass board represents zero intensity, while areas packed with parallel traces represent maximum intensity. Maps well to a continuous audio hum."\n'
            '    },\n'
            '    {\n'
            '      "title": "Component Solder Roughness",\n'
            '      "description": "Represents the physical bumps of soldered components vs flat board. Flat areas yield low values, while pins, chips, and solder joints yield high, sharp values. Ideal for triggering distinct haptic clicks or spikes."\n'
            '    }\n'
            '  ]\n'
            "}\n"
        )

        super().__init__(
            model_name=model_name,
            default_prompt=default_prompt or json_instruction,
        )

    def get_interest_factors(
        self,
        image_path: str,
        custom_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calls ImageAgent.analyze_image(...) and returns the parsed dictionary:
            {
                "image_context": "...",
                "interest_factors": [{"title": "...", "description": "..."}, ...]
            }
        """
        text = self.analyze_image(image_path, custom_prompt=custom_prompt)
    

        if isinstance(text, str) and text.startswith("Error:"):
            raise FileNotFoundError(text)

        data = self._safe_json_parse(text)

        context = data.get("image_context", "Unknown Context")
        factors = data.get("interest_factors", [])
        if not isinstance(factors, list):
            factors = []

        cleaned_factors: List[Dict[str, str]] = []
        for item in factors:
            if not isinstance(item, dict):
                continue
            
            title = item.get("title", "")
            desc = item.get("description", "")
            
            if isinstance(title, str) and title.strip():
                cleaned_factors.append({
                    "title": title.strip(),
                    "description": str(desc).strip()
                })

        # Hard cap at 6 factors
        return {
            "image_context": str(context).strip(),
            "interest_factors": cleaned_factors[:6]
        }

    @staticmethod
    def _safe_json_parse(text: str) -> Dict[str, Any]:
        if not isinstance(text, str):
            return {"image_context": "Parse Error", "interest_factors": []}

        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass

        return {"image_context": "Parse Error", "interest_factors": []}