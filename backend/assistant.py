import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=API_KEY) if API_KEY else None

MODEL = "llama-3.3-70b-versatile"


def generate_individual_response(
    user_message: str,
    data: Optional[Dict[str, Any]] = None,
) -> str:

    if client is None:
        return (
            "WindGuard AI is not configured.\n"
            "Please add GROQ_API_KEY to your .env file."
        )

    if data is None:
        system_prompt = """
You are WindGuard AI.

You are an agricultural consultant specializing ONLY in wind erosion.

If the user has not yet performed an analysis,
politely ask them to:

1. Select a region.
2. Run the analysis.
3. Then ask questions.

Always answer in English.

Maximum 60 words.
"""

    else:
        risk = round(data.get("risk_score", 0) * 100, 1)
        hotspots = data.get("hotspots_count", 0)
        context = data.get("context", {})
        feature_importances = data.get("feature_importances", {})
        top_features = ""

        if isinstance(feature_importances, dict):

            sorted_features = sorted(
                feature_importances.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]

            top_features = "\n".join(
                f"- {name}: {value:.3f}"
                for name, value in sorted_features
            )

        system_prompt = f"""
You are WindGuard AI.

You are a professional agronomist and environmental scientist.

Your ONLY specialization is wind erosion.

The following analysis has already been calculated.

Average wind erosion risk:
{risk}%

Hotspots detected:
{hotspots}

Context:
{context}

Most important environmental factors:
{top_features}

Rules:

- Answer ONLY in English.
- NEVER invent numbers.
- NEVER mention floods, earthquakes, tsunamis, oceans, hurricanes or unrelated disasters.
- Explain briefly what the calculated risk means.
- Mention the important environmental factors.
- Give practical agricultural recommendations.
- Recommend only realistic farming practices.
- Keep the response below 120 words.
- Maximum four bullet points.
- Use Markdown.
"""

    try:

        response = client.chat.completions.create(
            model=MODEL,
            temperature=0.1,
            top_p=0.9,
            max_tokens=220,
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
            "- Preserve crop residues.\n"
            "- Reduce intensive tillage."
        )

    except Exception as e:

        print(f"Groq API Error: {e}")

        return """
### WindGuard AI

The AI assistant is temporarily unavailable.

General recommendations:

- Preserve crop residues on the soil surface.
- Reduce intensive tillage.
- Use No-Till whenever possible.
- Plant shelterbelts to reduce wind speed.
"""