import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from groq import Groq


env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

MODEL = "llama-3.3-70b-versatile"


def generate_individual_response(
    user_message: str,
    data: Optional[Dict[str, Any]] = None,
) -> str:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        print("[ERROR] GROQ_API_KEY is missing from environment variables!")
        return (
            "WindGuard AI is not configured.\n"
            "Please add GROQ_API_KEY to your environment variables or .env file."
        )

    client = Groq(api_key=api_key)

    if data is None:
        system_prompt = """
You are WindGuard AI, an agricultural consultant specializing strictly in wind erosion.

The user has NOT run an analysis yet. 

Politely guide them to:
1. Select a geographical region on the map.
2. Run the analysis.
3. Ask any questions about wind erosion or soil protection once results are calculated.

Rules:
- Answer ONLY in English.
- Keep the tone helpful and professional.
- Max 60 words.
"""

    else:
        risk = round(data.get("risk_score", 0) * 100, 1)
        hotspots = data.get("hotspots_count", 0)
        context = data.get("context", {})
        feature_importances = data.get("feature_importances", {})
        top_features = "Not specified"

        if isinstance(feature_importances, dict) and feature_importances:
            sorted_features = sorted(
                feature_importances.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]

            top_features = "\n".join(
                f"- {name}: {value:.3f}" for name, value in sorted_features
            )

        system_prompt = f"""
You are WindGuard AI, an expert agronomist and environmental scientist specializing in soil conservation and wind erosion control.

REGION ANALYSIS CONTEXT:
- Calculated Average Wind Erosion Risk: {risk}%
- Hotspots Detected: {hotspots}
- Context Data: {context}
- Top Environmental Factors:
{top_features}

INSTRUCTIONS & RULES:
- Answer ONLY in English using clean Markdown formatting.
- Focus DIRECTLY on answering the user's specific question.
- Do NOT blindly start every response with a generic risk summary unless asked. Use the region analysis context above to inform and tailor your answers.
- If the user asks for "how-to" advice or specific agricultural techniques (e.g., planting windbreaks, tillage methods, cover crops), provide clear, practical, step-by-step guidance.
- Keep recommendations realistic for real-world farming.
- NEVER invent fake statistics or cite unrelated natural disasters (floods, tsunamis, earthquakes).
- Keep the response concise, structured, and under 180 words.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            top_p=0.9,
            max_tokens=300,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
        )

        answer = response.choices[0].message.content

        if answer:
            return answer.strip()

        return (
            "- Wind erosion analysis completed.\n"
            "- Preserve crop residues on the soil surface.\n"
            "- Reduce intensive tillage to protect soil structure."
        )

    except Exception as e:
        print(f"Groq API Error: {e}")

        return """
### WindGuard AI

The AI assistant is temporarily unavailable.

General Soil Protection Advice:
- Keep crop residues on the soil surface.
- Reduce tillage intensity or transition to No-Till.
- Plant multi-row shelterbelts perpendicular to prevailing winds.
"""