import asyncio
import websockets
import google.generativeai as genai
from PIL import Image
import io
import json
import sys
import re

# ----------------------------
# CONFIGURATION
# ----------------------------
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
WEBSOCKET_URI = "ws://raspberrypi.local:8765"  # Replace with Pi's IP if mDNS fails e.g. ws://192.168.1.x:8765

# Adjustable spatial resolution
ROWS = 2   # Change for testing (e.g., 3, 4, etc.)
COLS = 2   # Change for testing

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ----------------------------
# FLEXIBLE IMAGE SPLITTING
# ----------------------------
def split_image(image_path, rows=2, cols=2):
    """
    Splits image into rows x cols grid.
    Returns list of dictionaries:
    {
        "row": int,
        "col": int,
        "image": PIL.Image
    }
    """
    img = Image.open(image_path)
    width, height = img.size
    regions = []
    cell_w = width // cols
    cell_h = height // rows

    for r in range(rows):
        for c in range(cols):
            left = c * cell_w
            upper = r * cell_h
            right = (c + 1) * cell_w if c < cols - 1 else width
            lower = (r + 1) * cell_h if r < rows - 1 else height
            box = (left, upper, right, lower)
            cropped = img.crop(box)
            regions.append({
                "row": r,
                "col": c,
                "image": cropped
            })
    return regions

# ----------------------------
# CLEAN RAW GEMINI RESPONSE
# ----------------------------
def clean_json(raw):
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)

# ----------------------------
# GEMINI REGION DESCRIPTION
# ----------------------------
def describe_region(region_img, row, col):
    buffered = io.BytesIO()
    region_img.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()

    prompt = f"""
    You are analyzing a spatial quadrant of a larger interface.
    Describe clearly:
    - Objects
    - Charts
    - Text
    - UI elements
    - Visual importance
    Respond ONLY in JSON with no markdown formatting:
    {{
        "row": {row},
        "col": {col},
        "description": "",
        "importance_score": 0-10
    }}
    """

    response = model.generate_content(
        [prompt, {"mime_type": "image/png", "data": img_bytes}]
    )
    return response.text

# ----------------------------
# NORMALIZE IMPORTANCE SCORES
# ----------------------------
def normalize_scores(results):
    scores = [r["importance_score"] for r in results]
    min_s = min(scores)
    max_s = max(scores)
    for r in results:
        if max_s == min_s:
            r["normalized"] = 0.5
        else:
            r["normalized"] = (r["importance_score"] - min_s) / (max_s - min_s)
    return results

# ----------------------------
# SEND DATA TO RASPBERRY PI
# ----------------------------
async def send_to_hardware(data):
    try:
        async with websockets.connect(WEBSOCKET_URI) as websocket:
            await websocket.send(json.dumps(data))
            print("Data sent to Raspberry Pi successfully.")
    except Exception as e:
        print(f"Could not connect to Raspberry Pi: {e}")
        print("Check that the Pi is online and pi_server.py is running.")

# ----------------------------
# MAIN PIPELINE
# ----------------------------
async def process_image(image_path):
    print(f"Processing image: {image_path}")
    regions = split_image(image_path, rows=ROWS, cols=COLS)
    structured_results = []

    for region in regions:
        print(f"Analyzing region ({region['row']}, {region['col']})...")
        raw = describe_region(region["image"], region["row"], region["col"])
        try:
            parsed = clean_json(raw)
            structured_results.append(parsed)
            print(f"  → Importance score: {parsed['importance_score']}")
        except Exception as e:
            print(f"JSON parsing failed for region ({region['row']}, {region['col']}): {e}")
            print(f"  Raw response was: {raw}")

    if not structured_results:
        print("No valid Gemini outputs. Exiting.")
        return

    structured_results = normalize_scores(structured_results)
    print(f"\nAll regions analyzed. Sending {len(structured_results)} regions to Pi...")
    await send_to_hardware(structured_results)

# ----------------------------
# RUN PROGRAM
# ----------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python host_system.py <image_path>")
        print("Example: python host_system.py screenshot.png")
        sys.exit(1)

    image_path = sys.argv[1]
    asyncio.run(process_image(image_path))