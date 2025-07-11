from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, AnyUrl, Field
from typing import Dict, List
import string
import random

# Application metadata and OpenAPI tags
app = FastAPI(
    title="URL Shortener API",
    description="FastAPI backend service for URL shortening, redirection, and managing URL records.",
    version="1.0.0",
    openapi_tags=[
        {"name": "shortening", "description": "Shorten and manage URLs."},
        {"name": "redirect", "description": "Handle redirection from a short code to the original URL."}
    ]
)

# Simple in-memory store for demonstration (replace with DB in production)
url_store: Dict[str, Dict] = {}
reverse_url_store: Dict[str, str] = {}  # To check for duplicates

SHORTCODE_LENGTH = 6
ALPHABET = string.ascii_letters + string.digits

# PUBLIC_INTERFACE
class URLShortenRequest(BaseModel):
    """Request model for shortening URLs."""
    url: AnyUrl = Field(..., description="The original long URL to be shortened.")

# PUBLIC_INTERFACE
class URLShortenResponse(BaseModel):
    """Response model containing information about the shortened URL."""
    short_code: str = Field(..., description="The unique short code for the URL.")
    short_url: AnyUrl = Field(..., description="Full shortened URL including host.")
    url: AnyUrl = Field(..., description="The original long URL.")

# PUBLIC_INTERFACE
class URLRecord(BaseModel):
    """Model for a URL record as stored/reported by the API."""
    short_code: str = Field(..., description="Unique short code for the URL.")
    short_url: AnyUrl = Field(..., description="Full shortened URL including host.")
    url: AnyUrl = Field(..., description="Original long URL.")
    hits: int = Field(0, description="Number of times this short code was used for redirect.")

BASE_HOST = "http://localhost:8000"  # Change as appropriate for your environment

def _generate_short_code() -> str:
    """Generate a unique short code."""
    for _ in range(10):  # Try 10 times before error
        code = ''.join(random.choices(ALPHABET, k=SHORTCODE_LENGTH))
        if code not in url_store:
            return code
    raise RuntimeError("Unable to generate a unique short code.")

# PUBLIC_INTERFACE
@app.post("/shorten", response_model=URLShortenResponse, tags=["shortening"])
async def shorten_url(request: URLShortenRequest):
    """
    Shorten a long URL.
    - **url**: The long/original URL to shorten.
    Returns the short code and the shortened URL.
    """
    # Prevent duplicates (reuse same code for same URL)
    long_url = str(request.url)
    if long_url in reverse_url_store:
        code = reverse_url_store[long_url]
        record = url_store[code]
        return URLShortenResponse(
            short_code=code,
            short_url=f"{BASE_HOST}/{code}",
            url=record["url"]
        )
    code = _generate_short_code()
    url_store[code] = {
        "url": long_url,
        "hits": 0
    }
    reverse_url_store[long_url] = code
    return URLShortenResponse(
        short_code=code,
        short_url=f"{BASE_HOST}/{code}",
        url=long_url
    )

# PUBLIC_INTERFACE
@app.get("/{short_code}", status_code=status.HTTP_307_TEMPORARY_REDIRECT, tags=["redirect"])
async def redirect_to_original(short_code: str, request: Request):
    """
    Redirect to the original URL using the given short code.
    - **short_code**: Unique code for the shortened URL.
    Returns a temporary redirect response.
    """
    record = url_store.get(short_code)
    if not record:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    record["hits"] += 1
    return RedirectResponse(url=record["url"])

# PUBLIC_INTERFACE
@app.get("/api/urls", response_model=List[URLRecord], tags=["shortening"])
async def list_all_urls():
    """
    List all stored short URLs and their statistics.
    """
    result = []
    for code, data in url_store.items():
        result.append(
            URLRecord(
                short_code=code,
                short_url=f"{BASE_HOST}/{code}",
                url=data["url"],
                hits=data["hits"]
            )
        )
    return result

# PUBLIC_INTERFACE
@app.get("/api/urls/{short_code}", response_model=URLRecord, tags=["shortening"])
async def get_url_record(short_code: str):
    """
    Retrieve details on a specific short URL record.
    - **short_code**: Unique code for the shortened URL.
    """
    record = url_store.get(short_code)
    if not record:
        raise HTTPException(status_code=404, detail="Short URL not found.")
    return URLRecord(
        short_code=short_code,
        short_url=f"{BASE_HOST}/{short_code}",
        url=record["url"],
        hits=record["hits"]
    )

# PUBLIC_INTERFACE
@app.get("/", tags=["shortening"])
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}
