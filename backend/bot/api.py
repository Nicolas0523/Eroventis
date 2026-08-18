import asyncio
import time
import httpx

BASE_URL = "https://eroventis.onrender.com"

client = httpx.AsyncClient(
    timeout=httpx.Timeout(240),
    limits=httpx.Limits(
        max_connections=20,
        max_keepalive_connections=10,
    ),
)


async def poll_result(job_id: str, timeout: int = 120):
    start = time.time()

    while time.time() - start < timeout:
        try:
            response = await client.get(
                f"{BASE_URL}/analyze/status/{job_id}"
            )
        except httpx.HTTPError:
            await asyncio.sleep(2)
            continue

        if response.status_code == 404:
            return {"error": "Job not found."}

        if response.status_code != 200:
            await asyncio.sleep(2)
            continue

        result = response.json()
        status = result.get("status")

        if status == "done":
            return result

        if status == "error":
            return {
                "error": result.get("error", "Unknown server error")
            }

        await asyncio.sleep(3)

    return {"error": "Analysis timeout."}


async def _request(
    endpoint: str,
    polygon,
    start_date: str,
    end_date: str,
):
    payload = {
        "geometry": {
            "type": "Polygon",
            "coordinates": polygon,
        },
        "start_date": start_date,
        "end_date": end_date,
    }

    for attempt in range(3):
        try:
            response = await client.post(
                f"{BASE_URL}{endpoint}",
                json=payload,
            )

            response.raise_for_status()

            data = response.json()

            job_id = data.get("job_id")

            if not job_id:
                return {"error": "Server didn't return job_id."}

            return await poll_result(job_id)

        except httpx.HTTPError as e:
            if attempt == 2:
                if isinstance(e, httpx.HTTPStatusError):
                    return {
                        "error": f"HTTP {e.response.status_code}",
                        "details": e.response.text,
                    }

                return {"error": str(e)}

            await asyncio.sleep(2)

        except Exception as e:
            return {"error": str(e)}


async def analyze_region(polygon, start_date, end_date):
    return await _request(
        "/analyze",
        polygon,
        start_date,
        end_date,
    )


async def analyze_short(polygon, start_date, end_date):
    return await _request(
        "/analyze/short",
        polygon,
        start_date,
        end_date,
    )


async def analyze_climate(polygon, start_date, end_date):
    return await _request(
        "/analyze/climate",
        polygon,
        start_date,
        end_date,
    )


async def close_client():
    await client.aclose()