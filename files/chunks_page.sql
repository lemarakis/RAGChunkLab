
DROP TABLE IF EXISTS "public"."chunks_page";
CREATE TABLE "public"."chunks_page" (
  "id" SERIAL PRIMARY KEY,
  "content" text NOT NULL,
  "embedding" vector(1536),
  "metadata" jsonb DEFAULT '{}'::jsonb,
  "source" text,
  "created_at" timestamp(6) DEFAULT now()
);

CREATE INDEX ON chunks_page USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
