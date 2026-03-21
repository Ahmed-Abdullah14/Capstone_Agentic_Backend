from pydantic import BaseModel
from typing import Optional
from datetime import datetime

#------------------------------------------------------- Business Profiler Agent ----------------------------------------------------------

# Pydantic model to format Business Profiler Agent Response 
class BusinessProfilerResult(BaseModel):
    business_id: str

    # Pass contents directly to CompetitorAnalysisAgent cuz payload is small
    primary_hashtags: list[str]
    secondary_hashtags: list[str]
    location_keywords: list[str]
    exclude_accounts: list[str]
    ideal_follower_min: int
    ideal_follower_max: int

# ------------------------------------------------------ Competitor Analysis Agent --------------------------------------------------------

# Pydantic model to format Competitor Analysis Agent Response 
class CompetitorAnalysisResult(BaseModel):
    business_id: str
    success: bool

    # Payload is large so saved directly to DB and only metadata is returned
    competitor_count: int
    post_count: int
    message: str        # Returns message to manager so manager knows what to tell user, for ex "Found 10 competitors and scraped 100 posts."


# ----------------------------------------------------- Trend Analysis Agent ---------------------------------------------------------------

# Pydantic model needed to format Best Combinations, used in TrendSummary & TrendAnalysisResults
class BestCombination(BaseModel):
    image_style: str
    caption_style: str
    engagement_multiplier: float

# Pydantic model needed to format summary in TrendAnalysisResults
class TrendSummary(BaseModel):
    created_at: datetime
    visual_trends: list[str]
    caption_trends: list[str]
    hashtag_trends: list[str]
    posting_trends: list[str]
    best_combinations: list[BestCombination]        # Used from class above BestCombination(BaseModel)

# Pydantic model to format Trend Analysis Agent Response 
class TrendAnalysisResult(BaseModel):
    business_id: str
    success: bool
    image_cluster_count: int
    caption_cluster_count: int
    message: str        # Returns message to manager then manager returns to user, for ex "Identitifed 10 image clusters and 5 caption clusters"
    summary: Optional[TrendSummary] = None         # Used from class above TrendSummary(BaseModel)


# ---------------------------------------------------- Content Generator Agent ------------------------------------------------------------

# Pydantic model needed to format photo in ContentGeneratorResult
class PhotoDetails(BaseModel):
    angle: str
    instructions: str

# Pydantic model to format Content Generator Agent Response 
class ContentGeneratorResult(BaseModel):
    business_id: str
    success: bool
    content_response: str           # full narrative description of the post idea
    photo: PhotoDetails             # Used from class above PhotoDetails(BaseModel)   
    caption: str
    hashtags: list[str]
    generated_at: Optional[datetime] = None


# -------------------------------------------------------- Scheduler Agent --------------------------------------------------------------

# Pydantic model to Scheduler Agent Response 
class SchedulerResult(BaseModel):
    business_id: str
    success: bool
    scheduled_post_id: Optional[str] = None
    message: str        # Returns message to manager then manager returns to user, for ex "Post Scheduled for 8 am on Tuesday Mar 10th"

