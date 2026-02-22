import os
from PIL import Image
from dotenv import load_dotenv
from google import genai

class ImageAgent:
    def __init__(self, model_name="gemini-2.5-flash-lite", default_prompt="Can you explain what is happening in this image?"):
        """
        Initializes the ImageAgent with API keys, model selection, and a base prompt.
        """
        # Load environment variables from .env file
        load_dotenv()
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables.")

        # Initialize the GenAI client
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.default_prompt = default_prompt

    def analyze_image(self, image_path, custom_prompt=None):
        """
        Loads an image from a file path and sends it to Gemini for analysis.
        """
        try:
            # Load the local image using PIL
            image = Image.open(image_path)
            
            # Use custom prompt if provided, otherwise use the constructor's default
            prompt = custom_prompt if custom_prompt else self.default_prompt

            # Generate content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, image]
            )

            return response.text

        except FileNotFoundError:
            return f"Error: The file at {image_path} was not found."
        except Exception as e:
            return f"An error occurred: {str(e)}"

# --- Usage Example ---
if __name__ == "__main__":
    # Example initialization
    agent = ImageAgent(default_prompt="Describe this image in three bullet points.")
    
    # Path to your image
    path = "../Computer/images/image1.jpg"
    
    # Get response
    result = agent.analyze_image(path)
    print(result)