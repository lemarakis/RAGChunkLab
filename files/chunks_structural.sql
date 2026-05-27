
DROP TABLE IF EXISTS "public"."chunks_structural";
CREATE TABLE "public"."chunks_structural" (
  "id" SERIAL PRIMARY KEY,
  "course_title" text,
  "course_code" text,
  "content" text NOT NULL,
  "embedding" vector(1536),
  "metadata" jsonb DEFAULT '{}'::jsonb,
  "source" text,
  "created_at" timestamp(6) DEFAULT now()
);

CREATE INDEX ON chunks_structural USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
