from google import genai
from PIL import Image

from agents.interest_factors_agent import InterestFactorsAgent
import json

agent = InterestFactorsAgent()
path = "../Computer/images/image2.jpg"

try:
    factors = agent.get_interest_factors(path)
    print(json.dumps({"interest_factors": factors}, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Failed: {e}")