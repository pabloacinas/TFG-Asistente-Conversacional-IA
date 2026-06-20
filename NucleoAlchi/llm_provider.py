from google import genai
from google.genai.types import HttpOptions

from config import Config


def obtener_cliente():
    return genai.Client(
        vertexai=True,
        project=Config.GCP_PROJECT_ID,
        location=Config.GCP_LOCATION,
        http_options=HttpOptions(api_version="v1"),
    )
