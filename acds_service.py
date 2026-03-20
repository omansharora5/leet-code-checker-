import re
import asyncio
import httpx
from pydantic import BaseModel

class RawStats(BaseModel):
    easy: int
    medium: int
    hard: int

class ScoreBreakdown(BaseModel):
    effective_easies: float
    base_score: float
    hard_ratio: float
    depth_multiplier: float
    final_raw_score: float

class ACDSEvaluation(BaseModel):
    username: str
    raw_stats: RawStats
    scoring_breakdown: ScoreBreakdown
    job_fitness_percent: float

def extract_username(profile_input: str) -> str:
    """
    Extracts the LeetCode username from a valid URL or returns the input if it's already just a username.
    
    Examples:
        'https://leetcode.com/alfaarghya/' -> 'alfaarghya'
        'alfaarghya' -> 'alfaarghya'
        'leetcode.com/u/user123/' -> 'user123'
    """
    profile_input = profile_input.strip().rstrip('/')
    
    # Use regex to match leetcode.com/.../(username)
    match = re.search(r'leetcode\.com/(?:u/)?([^/]+)', profile_input)
    if match:
        return match.group(1)
        
    # If no URL match is found, assume the input itself is the direct username
    return profile_input

async def evaluate_candidate(profile_input: str) -> ACDSEvaluation:
    """
    Fetches a candidate's LeetCode stats from the public API and evaluates their fitness
    based on the Algorithmic Competency & Depth Score (ACDS).
    """
    username = extract_username(profile_input)
    api_url = f"https://alfa-leetcode-api.onrender.com/{username}/solved"
    
    # Fetch stats using an asynchronous HTTP client
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(api_url)
            
            # Raise an exception for standard HTTP error codes
            response.raise_for_status()
            data = response.json()
            
            # The API might return an HTTP 200 but contain an error payload if the user is invalid
            if 'errors' in data or data.get('easySolved') is None:
                raise ValueError(f"Failed to fetch stats for '{username}'. User may not exist or API returned an error.")
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"User '{username}' not found on LeetCode.")
            raise ValueError(f"API Error fetching stats for '{username}': HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            raise ValueError(f"Network request error while reaching the API: {str(e)}")
            
    # Safely extract solved counts
    easy = data.get("easySolved", 0)
    medium = data.get("mediumSolved", 0)
    hard = data.get("hardSolved", 0)
    
    # ACDS Algorithm Implementation
    
    # 1. The Easy Cap: Restrict padding by solving hundreds of easy questions
    effective_easies = min(float(easy), (float(medium) * 1.5) + 20.0)
    
    # 2. Base Score: Weighted calculation
    base_score = (effective_easies * 1.0) + (medium * 3.0) + (hard * 8.0)
    
    # 3. Depth Multiplier: Reward users who tackle hard problems relative to medium ones
    hard_ratio = hard / (medium + 1.0)
    depth_multiplier = min(1.0 + (hard_ratio * 2.0), 1.5)
    
    # 4. Final Raw Score
    final_raw_score = base_score * depth_multiplier
    
    # 5. Job Fitness Percentage: Benchmarked against a target score of 800
    fitness_percent = min((final_raw_score / 800.0) * 100.0, 100.0)
    
    return ACDSEvaluation(
        username=username,
        raw_stats=RawStats(easy=easy, medium=medium, hard=hard),
        scoring_breakdown=ScoreBreakdown(
            effective_easies=round(effective_easies, 2),
            base_score=round(base_score, 2),
            hard_ratio=round(hard_ratio, 4),
            depth_multiplier=round(depth_multiplier, 4),
            final_raw_score=round(final_raw_score, 2)
        ),
        job_fitness_percent=round(fitness_percent, 2)
    )

async def main():
    """
    Prompts the user for their LeetCode URL or username and evaluates their stats.
    """
    print("-" * 50)
    print("LeetCode ACDS Evaluator")
    print("-" * 50)
    
    user_input = input("Please enter your LeetCode URL or username: ").strip()
    
    if not user_input:
        print("No input provided. Exiting.")
        return
        
    print(f"\nEvaluating: '{user_input}'...")
    try:
        evaluation = await evaluate_candidate(user_input)
        print("Status: SUCCESS\n")
        print(evaluation.model_dump_json(indent=2))
    except Exception as e:
        print(f"Status: FAILED/ERROR")
        print(f"Details: {e}")

if __name__ == "__main__":
    # Ensure dependencies like httpx and pydantic are installed.
    # e.g., pip install httpx pydantic
    asyncio.run(main())
