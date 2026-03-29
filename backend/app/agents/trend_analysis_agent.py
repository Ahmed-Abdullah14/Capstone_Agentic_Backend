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
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
from collections import Counter
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
        competitor_posts = self.business_profiler_queries.get_competitor_posts(business_id)
        #competitor_posts = self.business_profiler_queries.get_competitor_posts_test(business_id)
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
        print(len(caption_data))
        #print()

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
        print(len(image_data))

        # Converting caption and image records to embedding matrices
        caption_embedding_records = []
        for record in caption_data:
            caption_embedding_records.append(record["embedding"])
        caption_embedding_matrix = np.array(caption_embedding_records)

        image_embedding_records = []
        for record in image_data:
            image_embedding_records.append(record["embedding"])
        image_embedding_matrix = np.array(image_embedding_records)

        # Applything PCA to reduce noise in data
        caption_embedding_matrix = self.reduce_dimensions(caption_embedding_matrix)
        image_embedding_matrix = self.reduce_dimensions(image_embedding_matrix)

        # Finding the optimal K value for K means 
        caption_cluster_k_value = self.find_best_k(caption_embedding_matrix)
        print(f"Best caption K: {caption_cluster_k_value}")
        image_cluster_k_value = self.find_best_k(image_embedding_matrix)
        print(f"Best Image K: {image_cluster_k_value}")

        # Running K means clustering
        caption_kmeans = KMeans(n_clusters=caption_cluster_k_value, random_state=42, n_init=10)
        image_kmeans = KMeans(n_clusters=image_cluster_k_value, random_state=42, n_init=10)

        caption_preds = caption_kmeans.fit_predict(caption_embedding_matrix)
        image_preds = image_kmeans.fit_predict(image_embedding_matrix)

        # Assigning cluster prediction ids to caption and image data records
        for i, record in enumerate(caption_data):
            record["cluster_id"] = int(caption_preds[i])
        
        for i, record in enumerate(image_data):
            record["cluster_id"] = int(image_preds[i])

        # Assigning a caption and image cluster id to each post 
        post_caption_cluster = {}
        for record in caption_data:
            post_caption_cluster[record["post_id"]] = record["cluster_id"]

        # A single post id can be linked to multiple image clusters ids because one post can have multiple images, each with a seperate cluster id
        # Find the most dominant id in the list of image cluster ids and assign that cluster id to the post
        post_clusters = {}
        for record in image_data:
            post_id = record["post_id"]
            cluster_id = record["cluster_id"]

            if post_id not in post_clusters:
                post_clusters[post_id] = []
            post_clusters[post_id].append(cluster_id)
        
        post_image_cluster = {}
        for post_id in post_clusters:
            clusters_list = post_clusters[post_id]
            post_image_cluster[post_id] = self.assign_dominant_cluster_id(clusters_list)
        
    
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
    
    # Finds best k value based on silhouette score
    def find_best_k(self, embeddings):
        si_scores = []
        for k in range(3,12):
            if k >= len(embeddings):
                break
            model = KMeans(n_clusters=k, random_state=42)
            preds = model.fit_predict(embeddings)
            si_score = silhouette_score(embeddings, preds)
            si_scores.append(si_score)
            print(f"k={k}, silhouette score={si_score:.4f}")
            

        best_k = si_scores.index(max(si_scores)) + 3
        return best_k
    
    # Applying PCA to reduce noise in data 
    def reduce_dimensions(self, embeddings):
        n_components = 35
        pca = PCA(n_components=n_components, random_state=42)
        return pca.fit_transform(embeddings)

    def assign_dominant_cluster_id(self, cluster_list):
        return Counter(cluster_list).most_common(1)[0][0]
        
