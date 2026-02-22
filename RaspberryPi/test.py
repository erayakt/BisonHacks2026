from google import genai
from PIL import Image

from agents.interest_factors_agent import InterestFactorsAgent
from agents.grid_scoring_agent import GridScoringAgent
import json


agent = InterestFactorsAgent()
path = "../Computer/images/image2.jpg"

"""
try:
    factors = agent.get_interest_factors(path)
    print(json.dumps({"interest_factors": factors}, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Failed: {e}")
"""

scorer = GridScoringAgent()
    
# Simulating pulling one point from your previous InterestFactorsAgent list
sample_factor = {
        "title": "Land Elevation Intensity",
    "description": "Represents the physical height above sea level, indicated by color gradients. Low intensity corresponds to sea level or lowlands (green areas), while high intensity corresponds to mountains (brown and dark yellow areas). This variation can control resistance."
}

try:
    results = scorer.score_grid("../Computer/images/image2.jpg", sample_factor)
    print(results["grid_matrix"])
    #print(json.dumps(results, indent=2))
except Exception as e:
    print(f"Failed: {e}")