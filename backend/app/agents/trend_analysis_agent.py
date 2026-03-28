import io
import httpx
import asyncio
import numpy as np
from openai import AsyncOpenAI
from app.agents.base_agent import Agent
from app.db.business_profiler_queries import BusinessProfilerQueries
from app.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, TEXT_EMBEDDING_MODEL, CLIP_MODEL, CLUSTER_LABEL_MODEL

import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize

class TrendAnalysisAgent(Agent):
    def __init__(self, kernel):
        super().__init__(kernel=kernel, name="trend_analysis_agent")

        self.business_profiler_queries = BusinessProfilerQueries()

        self._client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )

        self.clip_model = CLIPModel.from_pretrained(CLIP_MODEL)
        self.clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL)
        self.clip_model.eval()

    async def run(self, context):

        # Fetching competitors posts
        business_id = context.business_id
        #competitor_posts = self.business_profiler_queries.get_competitor_posts(business_id)
        competitor_posts = self.business_profiler_queries.get_competitor_posts_test(business_id)
        #print(competitor_posts)

        # Generating caption embeddings and saving it in a list of  dicitonaries
        post_ids = []
        captions = []
        caption_data = []
        for post in competitor_posts:
            caption = (post.get("caption") or "").strip()
            if caption:
                post_ids.append(post["id"])
                captions.append(caption)
        if captions:
            caption_embeddings = await self.embed_captions(captions)

            for i, embedding in enumerate(caption_embeddings):
                caption_data.append({"post_id": post_ids[i], "caption": captions[i], "embedding": embedding})
        
        # Debugging 
        #print(caption_data)
        #print()
        print(len(caption_data))

        # Downloading all images concurrently to reduce downloading bottleneck
        all_urls = []
        for post in competitor_posts:
            for image_url in post.get("image_urls") or []:
                all_urls.append(image_url)
        downloaded_urls = await self.download_all_images(all_urls)

        # Generating image embeddings and saving it in a list of dicitonaries
        image_data = []
        for post in competitor_posts:
            for image_url in post.get("image_urls") or []:
                if image_url in downloaded_urls:
                    image_bytes = downloaded_urls[image_url]
                    image_embedding = self.embed_image(image_bytes)
                    image_data.append({"post_id": post["id"], "image_url": image_url, "embedding": image_embedding}) 

        # Debugging
        #print (image_data)
        #print()
        print(len(image_data))

    
    # Creating embeddings for all captions
    async def embed_captions(self, captions):
        try:
            response = await self._client.embeddings.create(
                input = captions,
                model = TEXT_EMBEDDING_MODEL
            )
            return [item.embedding for item in response.data]
        except Exception:
            raise

    # Creating embeddings for a single image using catched image bytes
    def embed_image(self, image_bytes):
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            inputs = self.clip_processor(images=image, return_tensors="pt")

            with torch.no_grad():
                image_features = self.clip_model.get_image_features(**inputs)
                image_features = image_features.pooler_output

            image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
            image_embedding = image_features.squeeze().tolist()

            return image_embedding      
        except Exception:
            raise

    # Helper function to download images concurrently 
    async def download_all_images(self, urls):
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(*[self.download_image(client, url) for url in urls])
        return {url: content for url, content in results if content}
    
    # Helper function to download images concurrently 
    async def download_image(self, client, url):
        try:
            response = await client.get(url, timeout=10)
            return url, response.content
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            return url, None

