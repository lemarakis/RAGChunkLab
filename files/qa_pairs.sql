
DROP TABLE IF EXISTS "public"."qa_pairs";
CREATE TABLE "public"."qa_pairs" (
  "id" text COLLATE "pg_catalog"."default" PRIMARY KEY,
  "question" text COLLATE "pg_catalog"."default" NOT NULL,
  "answer" text COLLATE "pg_catalog"."default" NOT NULL,
  "approx_page" int4,
  "question_embedding" vector(1536),
  "answer_embedding" vector(1536),
  "source" text,
  "created_at" timestamp(6) DEFAULT now(),
  "updated_at" timestamp(6) DEFAULT now()
)
;
