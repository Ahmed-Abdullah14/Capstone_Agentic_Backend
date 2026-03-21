from app.db.supabase_client import supabase
from app.schemas.business_context import BusinessContext

# This file will have all DB functions related to the application 

class BusinessProfilerQueries:

    # DB Function to fetch business context
    def get_business_context(self, user_id, business_id):
        # Mocked data right now to get business context, once DB is connected it should get this from DB
        return BusinessContext(
            user_id=user_id,
            business_id=business_id,
            business_name="Downtown Calgary Cafe",
            business_type="Local Cafe Shop",
            location="Calgary, Alberta",
            target_customers="Students and young professionals",
            instagram_handle="downtown_cafe"
        )
    
    def get_scheduled_posts(self, date, business_id):    # fetch posts for a specific date
        pass
    def get_all_scheduled_posts(self, business_id):      # fetch all upcoming posts
        pass
    def cancel_scheduled_post(self, post_id):            # cancel/delete a scheduled post
        pass
    def schedule_post(self):                   # Creates a post table entry in DB
        pass
    def get_competitor_list(self, business_id):  # fetch existing competitor accounts from DB
        pass
    def get_competitor_posts(self, business_id): # fetch scraped competitor posts
        pass

    # HIGH PROPORTY
    def get_hashtags(self, business_id):        # Fetches hashtags for business from DB
        pass
    def get_trend_summary(self, business_id):   # Fetches Trend Summaries for business from DB
        pass

