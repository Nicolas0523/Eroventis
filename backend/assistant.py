import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from groq import Groq


env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


MODEL = "openai/gpt-oss-20b"


api_key = os.getenv("GROQ_API_KEY")
if api_key:
    client = Groq(api_key=api_key)
else:
    client = None
    print("[ERROR] GROQ_API_KEY is missing from environment variables!")


def generate_individual_response(
    user_message: str,
    data: Optional[Dict[str, Any]] = None,
) -> str:
    
    if not client:
        return (
            "WindGuard AI is not configured.\n"
            "Please add GROQ_API_KEY to your environment variables or .env file."
        )

    if data is None:
        system_prompt = """
You are WindGuard AI, an agricultural consultant specializing strictly in wind erosion prevention.

The user has NOT executed a regional analysis yet.

Politely guide them to:
1. Draw a polygon on the map to define their land area.
2. Click "Run AI Analysis".
3. Ask specific questions about erosion risks, crop protection, or mitigation techniques.

Rules:
- Answer ONLY in English.
- Professional, concise, welcoming tone.
- Max 50 words.
"""

    else:
        raw_risk = data.get("risk_score", 0)
        risk = round(raw_risk * 100, 1) if raw_risk <= 1.0 else round(raw_risk, 1)
        
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

ANALYSIS CONTEXT FOR SELECTED POLYGON:
- Overall Wind Erosion Risk: {risk}%
- Critical Hotspots Count: {hotspots}
- Regional Environmental Context: {context}
- Top Risk Driving Factors (SHAP/Feature Importance):
{top_features}

INSTRUCTIONS FOR INDIVIDUALIZED RECOMMENDATIONS:
1. Direct Answer: Answer the user's question directly.
2. Tailored Mitigation Strategy: Analyze the dominant risk drivers listed above:
   - If Wind Velocity / Wind Speed is high: Recommend shelterbelts (tree lines), strip cropping, or wind barrier layouts perpendicular to dominant winds.
   - If Vegetation Index (NDVI) is low: Recommend cover cropping (rye, clover), stubble retention, and avoiding bare fallow.
   - If Soil Moisture / Temperature / Aridity is critical: Recommend No-Till / Minimum Tillage, mulching, and moisture retention practices.
3. Specificity: Provide concrete, actionable, region-specific steps rather than generic platitudes.
4. Formatting: Use bullet points and bold key action terms. Keep response structured, professional, under 170 words, formatted in Markdown.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.25,
            top_p=0.9,
            max_tokens=350,
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
            "- Regional wind erosion analysis active.\n"
            "- Implement continuous soil cover and cover crops.\n"
            "- Reduce tillage intensity to maintain soil structure."
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