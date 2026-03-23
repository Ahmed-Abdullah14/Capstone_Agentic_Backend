-- ============================================================
-- LumenIQ Database Schema Reference (14 tables)
-- WARNING: This schema is for context only and is not meant to be run directly.
-- See supabase/migrations/001_initial_schema.sql for the runnable migration.
-- ============================================================

-- ENUM TYPES:
--   org_role: admin, member
--   run_status: queued, running, completed, failed
--   pipeline_stage: business_profiling, competitor_discovery, post_scraping, trend_analysis, content_generation, scheduling
--   cluster_type: image, caption
--   idea_status: pending, approved, rejected, used
--   scheduled_post_status: draft, scheduled, published, failed

-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.businesses (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  name text,
  business_type text,
  city text,
  country text,
  instagram_handle text,
  website_url text,
  ideal_customer text,
  profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  ig_user_id text,
  ig_business_account_id text,
  fb_page_id text,
  access_token text,
  token_expires_at timestamp with time zone,
  refresh_token text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT businesses_pkey PRIMARY KEY (id),
  CONSTRAINT businesses_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id)
);
CREATE TABLE public.clusters (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  business_id uuid NOT NULL,
  stage_run_id uuid,
  type USER-DEFINED NOT NULL,
  k integer NOT NULL,
  cluster_index integer NOT NULL,
  label text,
  rationale text,
  samples jsonb NOT NULL DEFAULT '[]'::jsonb,
  avg_engagement double precision,
  post_count integer,
  trend_score double precision,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT clusters_pkey PRIMARY KEY (id),
  CONSTRAINT clusters_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.businesses(id),
  CONSTRAINT clusters_stage_run_id_fkey FOREIGN KEY (stage_run_id) REFERENCES public.pipeline_stage_runs(id)
);
CREATE TABLE public.competitor_discovery_candidates (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL,
  candidate_username text NOT NULL,
  source jsonb NOT NULL DEFAULT '{}'::jsonb,
  classifier jsonb NOT NULL DEFAULT '{}'::jsonb,
  accepted boolean NOT NULL DEFAULT false,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT competitor_discovery_candidates_pkey PRIMARY KEY (id),
  CONSTRAINT competitor_discovery_candidates_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.pipeline_stage_runs(id)
);
CREATE TABLE public.competitors (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  business_id uuid NOT NULL,
  username text NOT NULL,
  profile_url text,
  follower_count bigint,
  post_count bigint,
  is_active boolean NOT NULL DEFAULT true,
  quality_flags jsonb NOT NULL DEFAULT '{}'::jsonb,
  discovered_from_run_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT competitors_pkey PRIMARY KEY (id),
  CONSTRAINT competitors_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.businesses(id),
  CONSTRAINT competitors_discovered_from_run_id_fkey FOREIGN KEY (discovered_from_run_id) REFERENCES public.pipeline_stage_runs(id)
);
CREATE TABLE public.content_calendars (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  business_id uuid NOT NULL,
  week_start_date date NOT NULL,
  priority_score double precision,
  meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  items jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT content_calendars_pkey PRIMARY KEY (id),
  CONSTRAINT content_calendars_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.businesses(id)
);
CREATE TABLE public.content_ideas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  business_id uuid NOT NULL,
  trend_summary_id uuid,
  title text NOT NULL,
  concept text,
  shot_list jsonb NOT NULL DEFAULT '[]'::jsonb,
  caption text,
  hashtags jsonb NOT NULL DEFAULT '[]'::jsonb,
  assets jsonb NOT NULL DEFAULT '{}'::jsonb,
  status USER-DEFINED NOT NULL DEFAULT 'pending'::idea_status,
  score double precision,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT content_ideas_pkey PRIMARY KEY (id),
  CONSTRAINT content_ideas_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.businesses(id),
  CONSTRAINT content_ideas_trend_summary_id_fkey FOREIGN KEY (trend_summary_id) REFERENCES public.trend_summaries(id)
);
CREATE TABLE public.idea_feedback (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  content_idea_id uuid NOT NULL,
  user_id uuid,
  rating integer CHECK (rating >= 1 AND rating <= 5),
  feedback text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT idea_feedback_pkey PRIMARY KEY (id),
  CONSTRAINT idea_feedback_content_idea_id_fkey FOREIGN KEY (content_idea_id) REFERENCES public.content_ideas(id),
  CONSTRAINT idea_feedback_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.org_members (
  org_id uuid NOT NULL,
  user_id uuid NOT NULL,
  role USER-DEFINED NOT NULL DEFAULT 'member'::org_role,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT org_members_pkey PRIMARY KEY (org_id, user_id),
  CONSTRAINT org_members_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id),
  CONSTRAINT org_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.organizations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT organizations_pkey PRIMARY KEY (id)
);
CREATE TABLE public.pipeline_runs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  business_id uuid NOT NULL,
  status USER-DEFINED NOT NULL DEFAULT 'queued'::run_status,
  params jsonb NOT NULL DEFAULT '{}'::jsonb,
  error jsonb,
  started_at timestamp with time zone,
  finished_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT pipeline_runs_pkey PRIMARY KEY (id),
  CONSTRAINT pipeline_runs_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.businesses(id)
);
CREATE TABLE public.pipeline_stage_runs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  pipeline_run_id uuid NOT NULL,
  stage USER-DEFINED NOT NULL,
  status USER-DEFINED NOT NULL DEFAULT 'queued'::run_status,
  params jsonb NOT NULL DEFAULT '{}'::jsonb,
  stats jsonb NOT NULL DEFAULT '{}'::jsonb,
  error jsonb,
  started_at timestamp with time zone,
  finished_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT pipeline_stage_runs_pkey PRIMARY KEY (id),
  CONSTRAINT pipeline_stage_runs_pipeline_run_id_fkey FOREIGN KEY (pipeline_run_id) REFERENCES public.pipeline_runs(id)
);
CREATE TABLE public.post_caption_embeddings (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  post_id uuid NOT NULL,
  embedding USER-DEFINED NOT NULL,
  model text NOT NULL DEFAULT 'text-embedding-3-small'::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT post_caption_embeddings_pkey PRIMARY KEY (id),
  CONSTRAINT post_caption_embeddings_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.posts(id)
);
CREATE TABLE public.post_cluster_assignments (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  stage_run_id uuid NOT NULL,
  post_id uuid NOT NULL,
  image_cluster_id uuid,
  caption_cluster_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT post_cluster_assignments_pkey PRIMARY KEY (id),
  CONSTRAINT post_cluster_assignments_stage_run_id_fkey FOREIGN KEY (stage_run_id) REFERENCES public.pipeline_stage_runs(id),
  CONSTRAINT post_cluster_assignments_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.posts(id),
  CONSTRAINT post_cluster_assignments_image_cluster_id_fkey FOREIGN KEY (image_cluster_id) REFERENCES public.clusters(id),
  CONSTRAINT post_cluster_assignments_caption_cluster_id_fkey FOREIGN KEY (caption_cluster_id) REFERENCES public.clusters(id)
);
CREATE TABLE public.post_image_embeddings (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  post_id uuid NOT NULL UNIQUE,
  embedding USER-DEFINED NOT NULL,
  model text NOT NULL DEFAULT 'openai/clip-vit-large-patch14'::text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT post_image_embeddings_pkey PRIMARY KEY (id),
  CONSTRAINT post_image_embeddings_post_id_fkey FOREIGN KEY (post_id) REFERENCES public.posts(id)
);
CREATE TABLE public.posts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  business_id uuid NOT NULL,
  competitor_id uuid NOT NULL,
  platform text NOT NULL DEFAULT 'instagram'::text,
  external_post_id text,
  permalink text,
  caption text,
  posted_at timestamp with time zone,
  media_type text,
  media jsonb NOT NULL DEFAULT '[]'::jsonb,
  hashtags ARRAY NOT NULL DEFAULT '{}'::text[],
  likes_count bigint DEFAULT 0,
  comments_count bigint DEFAULT 0,
  engagement_rate double precision,
  weighted_interactions double precision,
  wii double precision,
  is_selected boolean NOT NULL DEFAULT false,
  selection_meta jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT posts_pkey PRIMARY KEY (id),
  CONSTRAINT posts_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.businesses(id),
  CONSTRAINT posts_competitor_id_fkey FOREIGN KEY (competitor_id) REFERENCES public.competitors(id)
);
CREATE TABLE public.profiles (
  user_id uuid NOT NULL,
  display_name text,
  avatar_url text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (user_id),
  CONSTRAINT profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.publish_attempts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  scheduled_post_id uuid NOT NULL,
  attempt_no integer NOT NULL DEFAULT 1,
  requested_at timestamp with time zone NOT NULL DEFAULT now(),
  response jsonb,
  error jsonb,
  succeeded boolean NOT NULL DEFAULT false,
  CONSTRAINT publish_attempts_pkey PRIMARY KEY (id),
  CONSTRAINT publish_attempts_scheduled_post_id_fkey FOREIGN KEY (scheduled_post_id) REFERENCES public.scheduled_posts(id)
);
CREATE TABLE public.scheduled_posts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  business_id uuid NOT NULL,
  content_idea_id uuid,
  status USER-DEFINED NOT NULL DEFAULT 'draft'::scheduled_post_status,
  scheduled_at timestamp with time zone,
  approved_at timestamp with time zone,
  caption text,
  media jsonb NOT NULL DEFAULT '{}'::jsonb,
  publish_result jsonb,
  last_error jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT scheduled_posts_pkey PRIMARY KEY (id),
  CONSTRAINT scheduled_posts_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.businesses(id),
  CONSTRAINT scheduled_posts_content_idea_id_fkey FOREIGN KEY (content_idea_id) REFERENCES public.content_ideas(id)
);
CREATE TABLE public.trend_summaries (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  business_id uuid NOT NULL,
  stage_run_id uuid,
  summary jsonb NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT trend_summaries_pkey PRIMARY KEY (id),
  CONSTRAINT trend_summaries_business_id_fkey FOREIGN KEY (business_id) REFERENCES public.businesses(id),
  CONSTRAINT trend_summaries_stage_run_id_fkey FOREIGN KEY (stage_run_id) REFERENCES public.pipeline_stage_runs(id)
);