from google import genai
from PIL import Image

from agents.interest_factors_agent import InterestFactorsAgent
from agents.grid_scoring_agent import GridScoringAgent
import json


agent = InterestFactorsAgent()
path = "../Computer/images/image3.jpg"


try:
    factors = agent.get_interest_factors(path)
    print(json.dumps({"interest_factors": factors}, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Failed: {e}")


scorer = GridScoringAgent()
    
# Simulating pulling one point from your previous InterestFactorsAgent list
sample_factor = {
        "title": "Humidity Percentage Gradient",
        "description": "Represents the average relative humidity levels across the United States. Low intensity corresponds to areas with very low humidity (e.g., red regions <20%), and high intensity corresponds to areas with very high humidity (e.g., blue regions >80%). This can map to a continuous tone or vibration intensity."
}

try:
    results = scorer.score_grid("../Computer/images/image2.jpg", sample_factor)
    print(results["grid_matrix"])
    #print(json.dumps(results, indent=2))
except Exception as e:
    print(f"Failed: {e}")
