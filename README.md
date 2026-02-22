# VisionMouse

VisionMouse is a hardware + software system designed to help visually impaired users explore complex visual data such as charts, maps, dashboards, and technical drawings.

The system replaces slow, linear screen reader navigation with spatial exploration using tactile and adaptive audio feedback.

---

## Project Structure

VisionMouse/
   -> Computer/        # Desktop application (Debug UI + Keyboard Menu)
   -> RaspberryPi/     # Hardware node (motion tracking + tactile/audio output + AI Processing)

### Computer
- Desktop UI (PySide6)
- Screenshot capture
- Multi-agent Gemini image analysis
- Grid-based intensity + relevance mapping
- ElevenLabs text-to-speech and sound effects
- WebSocket communication with Raspberry Pi

### Raspberry Pi
- Optical motion / trackball input
- Servo motor tactile feedback
- Vibration motor support
- Speaker output
- Real-time feedback loop

---

## How It Works

1. The user captures a screenshot of visual content.
2. The system analyzes the image using a multi-agent pipeline powered by Gemini.
3. The user selects a factor to explore (e.g., intensity, density, borders).
4. Moving the device produces:
   - Continuous audio intensity changes
   - Tactile feedback for non-relevant areas
   - On-demand AI-generated descriptions

The grid-based approach allows fast spatial interaction without repeatedly sending cropped images to the model.

---

## Technologies Used

- Python
- Raspberry Pi 5
- PySide6
- Google Gemini API
- ElevenLabs API
- WebSockets
- GPIO / PWM control

---

## Running the Project

### Computer

cd Computer
pip install -r requirements.txt
python app.py

Create a `.env` file with:

GOOGLE_API_KEY=your_key
ELEVENLABS_API_KEY=your_key

### Raspberry Pi

cd RaspberryPi
pip install -r requirements.txt
python main.py

Ensure GPIO permissions, PWM, and audio output are configured properly.

---

VisionMouse is an experimental prototype developed for accessibility-focused exploration of visual data.
