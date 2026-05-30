/*
 Navicat Premium Dump SQL

 Source Server         : Docker_RAG_DB
 Source Server Type    : PostgreSQL
 Source Server Version : 160013 (160013)
 Source Host           : localhost:5432
 Source Catalog        : rag_db
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 160013 (160013)
 File Encoding         : 65001

 Date: 30/05/2026 20:49:45
*/


-- ----------------------------
-- Type structure for contracttype
-- ----------------------------
DROP TYPE IF EXISTS "public"."contracttype";
CREATE TYPE "public"."contracttype" AS ENUM (
  'PURCHASE',
  'SALES',
  'SERVICE',
  'LEASE',
  'EMPLOYMENT',
  'PARTNERSHIP',
  'LOAN',
  'OTHER'
);

-- ----------------------------
-- Type structure for failure_status_enum
-- ----------------------------
DROP TYPE IF EXISTS "public"."failure_status_enum";
CREATE TYPE "public"."failure_status_enum" AS ENUM (
  'PENDING',
  'ANALYZING',
  'FIXED',
  'IGNORED'
);

-- ----------------------------
-- Type structure for failure_type_enum
-- ----------------------------
DROP TYPE IF EXISTS "public"."failure_type_enum";
CREATE TYPE "public"."failure_type_enum" AS ENUM (
  'RETRIEVAL',
  'GENERATION',
  'HALLUCINATION',
  'INCOMPLETE',
  'IRRELEVANT',
  'OTHER'
);

-- ----------------------------
-- Type structure for feedback_type_enum
-- ----------------------------
DROP TYPE IF EXISTS "public"."feedback_type_enum";
CREATE TYPE "public"."feedback_type_enum" AS ENUM (
  'POSITIVE',
  'NEGATIVE',
  'NEUTRAL'
);

-- ----------------------------
-- Type structure for halfvec
-- ----------------------------
DROP TYPE IF EXISTS "public"."halfvec";
CREATE TYPE "public"."halfvec" (
  INPUT = "public"."halfvec_in",
  OUTPUT = "public"."halfvec_out",
  RECEIVE = "public"."halfvec_recv",
  SEND = "public"."halfvec_send",
  TYPMOD_IN = "public"."halfvec_typmod_in",
  INTERNALLENGTH = VARIABLE,
  STORAGE = external,
  CATEGORY = U,
  DELIMITER = ','
);

-- ----------------------------
-- Type structure for healthstatus
-- ----------------------------
DROP TYPE IF EXISTS "public"."healthstatus";
CREATE TYPE "public"."healthstatus" AS ENUM (
  'healthy',
  'warning',
  'critical',
  'caution',
  'unknown',
  'excellent'
);

-- ----------------------------
-- Type structure for improvement_type_enum
-- ----------------------------
DROP TYPE IF EXISTS "public"."improvement_type_enum";
CREATE TYPE "public"."improvement_type_enum" AS ENUM (
  'PROMPT',
  'RETRIEVAL',
  'CHUNKING',
  'PARAMETER',
  'OTHER'
);

-- ----------------------------
-- Type structure for reportperiod
-- ----------------------------
DROP TYPE IF EXISTS "public"."reportperiod";
CREATE TYPE "public"."reportperiod" AS ENUM (
  'daily',
  'weekly',
  'monthly',
  'quarterly',
  'yearly'
);

-- ----------------------------
-- Type structure for reviewstatus
-- ----------------------------
DROP TYPE IF EXISTS "public"."reviewstatus";
CREATE TYPE "public"."reviewstatus" AS ENUM (
  'PENDING',
  'IN_PROGRESS',
  'APPROVED',
  'REJECTED',
  'NEEDS_REVISION'
);

-- ----------------------------
-- Type structure for risklevel
-- ----------------------------
DROP TYPE IF EXISTS "public"."risklevel";
CREATE TYPE "public"."risklevel" AS ENUM (
  'LOW',
  'MEDIUM',
  'HIGH',
  'CRITICAL'
);

-- ----------------------------
-- Type structure for sparsevec
-- ----------------------------
DROP TYPE IF EXISTS "public"."sparsevec";
CREATE TYPE "public"."sparsevec" (
  INPUT = "public"."sparsevec_in",
  OUTPUT = "public"."sparsevec_out",
  RECEIVE = "public"."sparsevec_recv",
  SEND = "public"."sparsevec_send",
  TYPMOD_IN = "public"."sparsevec_typmod_in",
  INTERNALLENGTH = VARIABLE,
  STORAGE = external,
  CATEGORY = U,
  DELIMITER = ','
);

-- ----------------------------
-- Type structure for task_priority_enum
-- ----------------------------
DROP TYPE IF EXISTS "public"."task_priority_enum";
CREATE TYPE "public"."task_priority_enum" AS ENUM (
  'low',
  'normal',
  'high',
  'urgent'
);

-- ----------------------------
-- Type structure for task_status_enum
-- ----------------------------
DROP TYPE IF EXISTS "public"."task_status_enum";
CREATE TYPE "public"."task_status_enum" AS ENUM (
  'pending',
  'running',
  'completed',
  'failed',
  'cancelled',
  'interrupted'
);

-- ----------------------------
-- Type structure for vector
-- ----------------------------
DROP TYPE IF EXISTS "public"."vector";
CREATE TYPE "public"."vector" (
  INPUT = "public"."vector_in",
  OUTPUT = "public"."vector_out",
  RECEIVE = "public"."vector_recv",
  SEND = "public"."vector_send",
  TYPMOD_IN = "public"."vector_typmod_in",
  INTERNALLENGTH = VARIABLE,
  STORAGE = external,
  CATEGORY = U,
  DELIMITER = ','
);

-- ----------------------------
-- Table structure for agent_collaborations
-- ----------------------------
DROP TABLE IF EXISTS "public"."agent_collaborations";
CREATE TABLE "public"."agent_collaborations" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "task_id" uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "from_agent" varchar(50) COLLATE "pg_catalog"."default",
  "to_agent" varchar(50) COLLATE "pg_catalog"."default",
  "message_type" varchar(20) COLLATE "pg_catalog"."default",
  "message_content" jsonb,
  "timestamp" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for agent_steps
-- ----------------------------
DROP TABLE IF EXISTS "public"."agent_steps";
CREATE TABLE "public"."agent_steps" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "trace_id" uuid NOT NULL,
  "step_number" int4 NOT NULL,
  "step_type" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "tool_name" varchar COLLATE "pg_catalog"."default",
  "tool_input" jsonb,
  "tool_output" text COLLATE "pg_catalog"."default",
  "tool_duration" float8,
  "confidence" float8,
  "metadata" jsonb,
  "timestamp" float8 NOT NULL,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "step_metadata" json,
  "user_id" uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'default'::character varying
)
;

-- ----------------------------
-- Table structure for agent_task_checkpoints
-- ----------------------------
DROP TABLE IF EXISTS "public"."agent_task_checkpoints";
CREATE TABLE "public"."agent_task_checkpoints" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "task_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "checkpoint_id" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "parent_checkpoint_id" varchar(255) COLLATE "pg_catalog"."default",
  "node_name" varchar(100) COLLATE "pg_catalog"."default",
  "state_data" jsonb NOT NULL,
  "extra_metadata" jsonb,
  "created_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Table structure for agent_task_events
-- ----------------------------
DROP TABLE IF EXISTS "public"."agent_task_events";
CREATE TABLE "public"."agent_task_events" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "task_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "event_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "event_data" jsonb,
  "node_name" varchar(100) COLLATE "pg_catalog"."default",
  "event_message" varchar(500) COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Table structure for agent_task_status
-- ----------------------------
DROP TABLE IF EXISTS "public"."agent_task_status";
CREATE TABLE "public"."agent_task_status" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "task_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "thread_id" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" uuid,
  "request_id" varchar(100) COLLATE "pg_catalog"."default",
  "task_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "task_name" varchar(255) COLLATE "pg_catalog"."default",
  "status" "public"."task_status_enum" NOT NULL DEFAULT 'pending'::task_status_enum,
  "priority" "public"."task_priority_enum" NOT NULL DEFAULT 'normal'::task_priority_enum,
  "user_query" text COLLATE "pg_catalog"."default",
  "final_response" text COLLATE "pg_catalog"."default",
  "current_node" varchar(100) COLLATE "pg_catalog"."default",
  "progress_percent" int4 DEFAULT 0,
  "progress_message" varchar(500) COLLATE "pg_catalog"."default",
  "specialist_progress" jsonb,
  "error_message" text COLLATE "pg_catalog"."default",
  "retry_count" int4 DEFAULT 0,
  "max_retries" int4 DEFAULT 3,
  "execution_time_ms" float8 DEFAULT 0.0,
  "arq_job_id" varchar(100) COLLATE "pg_catalog"."default",
  "checkpoint_id" varchar(255) COLLATE "pg_catalog"."default",
  "extra_metadata" jsonb,
  "created_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "started_at" timestamptz(6),
  "completed_at" timestamptz(6),
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "needs_clarification" bool DEFAULT false,
  "clarification_request" jsonb,
  "intent_analysis" jsonb
)
;

-- ----------------------------
-- Table structure for agent_traces
-- ----------------------------
DROP TABLE IF EXISTS "public"."agent_traces";
CREATE TABLE "public"."agent_traces" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "session_id" uuid,
  "message_id" uuid,
  "agent_type" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "user_query" text COLLATE "pg_catalog"."default" NOT NULL,
  "final_answer" text COLLATE "pg_catalog"."default",
  "total_iterations" int4 DEFAULT 0,
  "total_time" float8 DEFAULT 0.0,
  "tool_calls_count" int4 DEFAULT 0,
  "status" varchar COLLATE "pg_catalog"."default" DEFAULT 'running'::character varying,
  "error_message" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "completed_at" timestamptz(6),
  "user_id" uuid NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'default'::character varying,
  "langsmith_run_id" varchar COLLATE "pg_catalog"."default",
  "model_name" varchar(200) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for alembic_version
-- ----------------------------
DROP TABLE IF EXISTS "public"."alembic_version";
CREATE TABLE "public"."alembic_version" (
  "version_num" varchar(32) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Table structure for audit_results
-- ----------------------------
DROP TABLE IF EXISTS "public"."audit_results";
CREATE TABLE "public"."audit_results" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "task_id" uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "agent_name" varchar(50) COLLATE "pg_catalog"."default",
  "findings" jsonb,
  "risk_score" float8,
  "confidence" float8,
  "recommendations" jsonb,
  "legal_basis" jsonb,
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for audit_tasks
-- ----------------------------
DROP TABLE IF EXISTS "public"."audit_tasks";
CREATE TABLE "public"."audit_tasks" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "user_id" uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "audit_type" varchar(50) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'pending'::character varying,
  "documents" jsonb,
  "created_at" timestamptz(6) DEFAULT now(),
  "completed_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for chat_groups
-- ----------------------------
DROP TABLE IF EXISTS "public"."chat_groups";
CREATE TABLE "public"."chat_groups" (
  "id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "description" varchar COLLATE "pg_catalog"."default",
  "avatar_url" varchar COLLATE "pg_catalog"."default",
  "status" varchar COLLATE "pg_catalog"."default" DEFAULT 'active'::character varying,
  "created_by" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "settings" jsonb DEFAULT '{"max_members": 100, "require_approval": false, "allow_member_invite": true}'::jsonb,
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "archived_at" timestamp(6)
)
;

-- ----------------------------
-- Table structure for chat_messages
-- ----------------------------
DROP TABLE IF EXISTS "public"."chat_messages";
CREATE TABLE "public"."chat_messages" (
  "id" uuid NOT NULL,
  "session_id" uuid,
  "role" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "sources" json,
  "created_at" timestamptz(6) DEFAULT now(),
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default",
  "importance" float8 DEFAULT 0.5,
  "access_count" int4 DEFAULT 0,
  "last_accessed" timestamptz(6) DEFAULT now(),
  "embedding" "public"."vector",
  "prompt_tokens" int4,
  "completion_tokens" int4,
  "total_tokens" int4,
  "model_name" varchar(100) COLLATE "pg_catalog"."default",
  "agent_name" varchar(100) COLLATE "pg_catalog"."default",
  "turn" int4 DEFAULT 1,
  "session_total_tokens" int4
)
;

-- ----------------------------
-- Table structure for chat_sessions
-- ----------------------------
DROP TABLE IF EXISTS "public"."chat_sessions";
CREATE TABLE "public"."chat_sessions" (
  "id" uuid NOT NULL,
  "user_id" uuid,
  "title" varchar COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6),
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for contract_clauses
-- ----------------------------
DROP TABLE IF EXISTS "public"."contract_clauses";
CREATE TABLE "public"."contract_clauses" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "report_id" uuid NOT NULL,
  "clause_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "clause_title" varchar(255) COLLATE "pg_catalog"."default",
  "clause_text" text COLLATE "pg_catalog"."default" NOT NULL,
  "original_position" int4,
  "page_number" int4,
  "risk_level" varchar(50) COLLATE "pg_catalog"."default",
  "risk_score" float8,
  "is_standard" bool DEFAULT false,
  "is_controversial" bool DEFAULT false,
  "needs_attention" bool DEFAULT false,
  "analysis" jsonb,
  "suggestions" jsonb,
  "created_at" timestamptz(6) NOT NULL DEFAULT now()
)
;

-- ----------------------------
-- Table structure for contract_comparison_history
-- ----------------------------
DROP TABLE IF EXISTS "public"."contract_comparison_history";
CREATE TABLE "public"."contract_comparison_history" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "comparison_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "contract1_id" uuid NOT NULL,
  "contract2_id" uuid NOT NULL,
  "comparison_result" jsonb,
  "differences" jsonb,
  "similarity_score" float8,
  "summary" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) NOT NULL DEFAULT now()
)
;

-- ----------------------------
-- Table structure for contract_review_reports
-- ----------------------------
DROP TABLE IF EXISTS "public"."contract_review_reports";
CREATE TABLE "public"."contract_review_reports" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "contract_name" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "contract_type" varchar(50) COLLATE "pg_catalog"."default",
  "counterparty" varchar(255) COLLATE "pg_catalog"."default",
  "contract_value" float8,
  "currency" varchar(10) COLLATE "pg_catalog"."default" DEFAULT 'CNY'::character varying,
  "original_text" text COLLATE "pg_catalog"."default",
  "review_status" varchar(50) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "overall_risk_score" float8,
  "overall_risk_level" varchar(50) COLLATE "pg_catalog"."default",
  "basic_analysis" jsonb,
  "parties_info" jsonb,
  "effective_date" timestamptz(6),
  "expiration_date" timestamptz(6),
  "termination_conditions" jsonb,
  "clauses_analysis" jsonb,
  "risk_clauses" jsonb,
  "unfavorable_clauses" jsonb,
  "compliance_checks" jsonb,
  "comparison_result" jsonb,
  "suggestions" jsonb,
  "recommended_revisions" jsonb,
  "ai_analysis_summary" text COLLATE "pg_catalog"."default",
  "pdf_path" varchar(1000) COLLATE "pg_catalog"."default",
  "review_completed_at" timestamptz(6),
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "updated_at" timestamptz(6),
  "expires_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for contract_templates
-- ----------------------------
DROP TABLE IF EXISTS "public"."contract_templates";
CREATE TABLE "public"."contract_templates" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "contract_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "template_content" text COLLATE "pg_catalog"."default" NOT NULL,
  "clauses_library" jsonb,
  "usage_count" int4 DEFAULT 0,
  "is_public" bool DEFAULT false,
  "created_by" uuid,
  "updated_by" uuid,
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "updated_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for custom_tools
-- ----------------------------
DROP TABLE IF EXISTS "public"."custom_tools";
CREATE TABLE "public"."custom_tools" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(80) COLLATE "pg_catalog"."default" NOT NULL,
  "display_name" varchar(120) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default" NOT NULL,
  "purpose" text COLLATE "pg_catalog"."default",
  "kind" varchar(32) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'echo'::character varying,
  "status" varchar(32) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'draft'::character varying,
  "version" varchar(32) COLLATE "pg_catalog"."default" NOT NULL DEFAULT '1.0.0'::character varying,
  "input_schema" jsonb NOT NULL DEFAULT '{}'::jsonb,
  "output_schema" jsonb NOT NULL DEFAULT '{}'::jsonb,
  "runtime_config" jsonb NOT NULL DEFAULT '{}'::jsonb,
  "safety_policy" jsonb NOT NULL DEFAULT '{}'::jsonb,
  "generated_code" text COLLATE "pg_catalog"."default",
  "agent_id" varchar(100) COLLATE "pg_catalog"."default",
  "created_by" varchar(64) COLLATE "pg_catalog"."default",
  "approved_by" varchar(64) COLLATE "pg_catalog"."default",
  "enabled" bool NOT NULL DEFAULT false,
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "updated_at" timestamptz(6) NOT NULL DEFAULT now()
)
;

-- ----------------------------
-- Table structure for document_chunks
-- ----------------------------
DROP TABLE IF EXISTS "public"."document_chunks";
CREATE TABLE "public"."document_chunks" (
  "id" uuid NOT NULL,
  "document_id" uuid NOT NULL,
  "chunk_index" int4 NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "meta_info" jsonb,
  "created_at" timestamptz(6) DEFAULT now(),
  "heading_path" varchar COLLATE "pg_catalog"."default",
  "chunk_start" int4,
  "chunk_end" int4,
  "token_count" int4,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default",
  "fts_vector" tsvector,
  "embedding" "public"."vector",
  "content_tsvector" tsvector GENERATED ALWAYS AS (
to_tsvector('simple'::regconfig, COALESCE(content, ''::text))
) STORED,
  "domain" varchar(20) COLLATE "pg_catalog"."default",
  "node_type" varchar(10) COLLATE "pg_catalog"."default",
  "summary" varchar(500) COLLATE "pg_catalog"."default",
  "relationships" jsonb DEFAULT '{}'::jsonb,
  "node_hash" varchar(64) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for documents
-- ----------------------------
DROP TABLE IF EXISTS "public"."documents";
CREATE TABLE "public"."documents" (
  "id" uuid NOT NULL,
  "kb_id" uuid,
  "filename" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "hash" varchar(32) COLLATE "pg_catalog"."default",
  "file_path" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "file_type" varchar(200) COLLATE "pg_catalog"."default",
  "file_size" int4,
  "status" varchar(20) COLLATE "pg_catalog"."default",
  "error_msg" text COLLATE "pg_catalog"."default",
  "meta_info" jsonb,
  "created_at" timestamptz(6) DEFAULT now(),
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default",
  "user_id" uuid,
  "visibility" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'private'::character varying,
  "embedding" "public"."halfvec",
  "processing_state" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'pending'::character varying,
  "processing_progress" int4 DEFAULT 0,
  "processing_message" varchar(255) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for enrichment_jobs
-- ----------------------------
DROP TABLE IF EXISTS "public"."enrichment_jobs";
CREATE TABLE "public"."enrichment_jobs" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "document_id" uuid NOT NULL,
  "job_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "domain" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'pending'::character varying,
  "payload" jsonb DEFAULT '{}'::jsonb,
  "error_message" text COLLATE "pg_catalog"."default",
  "retry_count" int4 DEFAULT 0,
  "max_retries" int4 DEFAULT 5,
  "next_retry_at" timestamptz(6),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for enterprise_policy_matches
-- ----------------------------
DROP TABLE IF EXISTS "public"."enterprise_policy_matches";
CREATE TABLE "public"."enterprise_policy_matches" (
  "id" uuid NOT NULL,
  "enterprise_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "policy_id" uuid NOT NULL,
  "match_score" float8,
  "match_status" varchar(20) COLLATE "pg_catalog"."default",
  "notification_status" varchar(20) COLLATE "pg_catalog"."default",
  "match_reasons" varchar(500)[] COLLATE "pg_catalog"."default",
  "acknowledged" bool,
  "acknowledged_at" timestamp(6),
  "meta_info" json,
  "created_at" timestamp(6),
  "updated_at" timestamp(6),
  "notified_at" timestamp(6),
  "dismissed_at" timestamp(6),
  "feedback" jsonb DEFAULT '{}'::jsonb
)
;

-- ----------------------------
-- Table structure for episodic_memories
-- ----------------------------
DROP TABLE IF EXISTS "public"."episodic_memories";
CREATE TABLE "public"."episodic_memories" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "session_id" uuid,
  "user_id" uuid,
  "role" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "sources" jsonb,
  "embedding" "public"."vector",
  "importance" float8 DEFAULT 0.5,
  "access_count" int4 DEFAULT 0,
  "last_accessed" timestamptz(6) DEFAULT now(),
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for failure_cases
-- ----------------------------
DROP TABLE IF EXISTS "public"."failure_cases";
CREATE TABLE "public"."failure_cases" (
  "id" uuid NOT NULL,
  "feedback_id" uuid NOT NULL,
  "failure_type" "public"."failure_type_enum" NOT NULL,
  "analysis" jsonb,
  "fix_suggestions" jsonb,
  "status" "public"."failure_status_enum" NOT NULL,
  "auto_analyzed" bool,
  "confidence_score" int4,
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6),
  "analyzed_at" timestamptz(6)
)
;
COMMENT ON COLUMN "public"."failure_cases"."failure_type" IS '失败类型';
COMMENT ON COLUMN "public"."failure_cases"."analysis" IS '分析结果（根因、缺失信息等）';
COMMENT ON COLUMN "public"."failure_cases"."fix_suggestions" IS '修复建议列表';
COMMENT ON COLUMN "public"."failure_cases"."status" IS '处理状态';
COMMENT ON COLUMN "public"."failure_cases"."auto_analyzed" IS '是否已自动分析';
COMMENT ON COLUMN "public"."failure_cases"."confidence_score" IS '分析置信度 0-100';
COMMENT ON COLUMN "public"."failure_cases"."analyzed_at" IS '分析时间';

-- ----------------------------
-- Table structure for financial_anomaly_records
-- ----------------------------
DROP TABLE IF EXISTS "public"."financial_anomaly_records";
CREATE TABLE "public"."financial_anomaly_records" (
  "id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "report_id" uuid,
  "anomaly_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "anomaly_category" varchar(50) COLLATE "pg_catalog"."default",
  "severity" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "confidence" float8,
  "title" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "detected_value" float8,
  "expected_value" float8,
  "deviation" float8,
  "deviation_percentage" float8,
  "affected_accounts" jsonb,
  "related_transactions" jsonb,
  "recommended_actions" jsonb,
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'detected'::character varying,
  "acknowledged" bool DEFAULT false,
  "acknowledged_by" uuid,
  "acknowledged_at" timestamptz(6),
  "created_at" timestamptz(6) NOT NULL,
  "resolved_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for financial_data_history
-- ----------------------------
DROP TABLE IF EXISTS "public"."financial_data_history";
CREATE TABLE "public"."financial_data_history" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "financial_data_id" uuid NOT NULL,
  "modified_by" uuid NOT NULL,
  "modified_at" timestamptz(6) DEFAULT now(),
  "previous_data" jsonb NOT NULL,
  "new_data" jsonb NOT NULL,
  "change_reason" text COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for financial_health_reports
-- ----------------------------
DROP TABLE IF EXISTS "public"."financial_health_reports";
CREATE TABLE "public"."financial_health_reports" (
  "id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "report_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "report_period" "public"."reportperiod" NOT NULL,
  "period_start" timestamptz(6) NOT NULL,
  "period_end" timestamptz(6) NOT NULL,
  "overall_health_score" float8,
  "health_status" "public"."healthstatus",
  "revenue_summary" jsonb,
  "expense_summary" jsonb,
  "profit_summary" jsonb,
  "cash_flow_summary" jsonb,
  "financial_metrics" jsonb,
  "trend_indicators" jsonb,
  "anomaly_detections" jsonb,
  "risk_assessments" jsonb,
  "recommendations" jsonb,
  "revenue_data" jsonb,
  "expense_data" jsonb,
  "generated_by" varchar(50) COLLATE "pg_catalog"."default" DEFAULT 'system'::character varying,
  "source_data_description" text COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'completed'::character varying,
  "created_at" timestamptz(6) NOT NULL,
  "completed_at" timestamptz(6),
  "expires_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for financial_thresholds
-- ----------------------------
DROP TABLE IF EXISTS "public"."financial_thresholds";
CREATE TABLE "public"."financial_thresholds" (
  "id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "metric_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "metric_category" varchar(50) COLLATE "pg_catalog"."default",
  "warning_threshold" float8,
  "critical_threshold" float8,
  "comparison_operator" varchar(10) COLLATE "pg_catalog"."default" DEFAULT '>'::character varying,
  "enabled" bool DEFAULT true,
  "created_by" uuid,
  "updated_by" uuid,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL
)
;

-- ----------------------------
-- Table structure for financial_trend_data
-- ----------------------------
DROP TABLE IF EXISTS "public"."financial_trend_data";
CREATE TABLE "public"."financial_trend_data" (
  "id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "metric_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "metric_category" varchar(50) COLLATE "pg_catalog"."default",
  "metric_value" float8 NOT NULL,
  "metric_unit" varchar(20) COLLATE "pg_catalog"."default",
  "record_date" timestamptz(6) NOT NULL,
  "period_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "meta_data" jsonb,
  "source" varchar(50) COLLATE "pg_catalog"."default" DEFAULT 'calculated'::character varying,
  "created_at" timestamptz(6) NOT NULL
)
;

-- ----------------------------
-- Table structure for group_invitations
-- ----------------------------
DROP TABLE IF EXISTS "public"."group_invitations";
CREATE TABLE "public"."group_invitations" (
  "id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "group_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "invitee_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "inviter_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar COLLATE "pg_catalog"."default" DEFAULT 'pending'::character varying,
  "message" varchar COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "expires_at" timestamp(6),
  "responded_at" timestamp(6)
)
;

-- ----------------------------
-- Table structure for group_members
-- ----------------------------
DROP TABLE IF EXISTS "public"."group_members";
CREATE TABLE "public"."group_members" (
  "id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "group_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "role" varchar COLLATE "pg_catalog"."default" DEFAULT 'member'::character varying,
  "status" varchar COLLATE "pg_catalog"."default" DEFAULT 'active'::character varying,
  "invited_by" varchar COLLATE "pg_catalog"."default",
  "joined_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "left_at" timestamp(6),
  "notification_settings" jsonb DEFAULT '{"all_messages": true, "mentions_only": false}'::jsonb
)
;

-- ----------------------------
-- Table structure for group_messages
-- ----------------------------
DROP TABLE IF EXISTS "public"."group_messages";
CREATE TABLE "public"."group_messages" (
  "id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "group_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "sender_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "content_type" varchar COLLATE "pg_catalog"."default" DEFAULT 'text'::character varying,
  "metadata" jsonb DEFAULT '{}'::jsonb,
  "is_deleted" bool DEFAULT false,
  "is_edited" bool DEFAULT false,
  "edited_at" timestamp(6),
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Table structure for improvement_records
-- ----------------------------
DROP TABLE IF EXISTS "public"."improvement_records";
CREATE TABLE "public"."improvement_records" (
  "id" uuid NOT NULL,
  "failure_case_id" uuid NOT NULL,
  "improvement_type" "public"."improvement_type_enum" NOT NULL,
  "before_config" jsonb,
  "after_config" jsonb,
  "ab_test_result" jsonb,
  "deployed" bool,
  "deployed_at" timestamptz(6),
  "success_rate_before" int4,
  "success_rate_after" int4,
  "user_satisfaction_before" int4,
  "user_satisfaction_after" int4,
  "description" text COLLATE "pg_catalog"."default",
  "notes" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6)
)
;
COMMENT ON COLUMN "public"."improvement_records"."improvement_type" IS '改进类型';
COMMENT ON COLUMN "public"."improvement_records"."before_config" IS '改进前配置';
COMMENT ON COLUMN "public"."improvement_records"."after_config" IS '改进后配置';
COMMENT ON COLUMN "public"."improvement_records"."ab_test_result" IS 'A/B 测试结果';
COMMENT ON COLUMN "public"."improvement_records"."deployed" IS '是否已部署';
COMMENT ON COLUMN "public"."improvement_records"."deployed_at" IS '部署时间';
COMMENT ON COLUMN "public"."improvement_records"."success_rate_before" IS '改进前成功率 %';
COMMENT ON COLUMN "public"."improvement_records"."success_rate_after" IS '改进后成功率 %';
COMMENT ON COLUMN "public"."improvement_records"."user_satisfaction_before" IS '改进前用户满意度 0-100';
COMMENT ON COLUMN "public"."improvement_records"."user_satisfaction_after" IS '改进后用户满意度 0-100';
COMMENT ON COLUMN "public"."improvement_records"."description" IS '改进描述';
COMMENT ON COLUMN "public"."improvement_records"."notes" IS '备注';

-- ----------------------------
-- Table structure for invite_code_usages
-- ----------------------------
DROP TABLE IF EXISTS "public"."invite_code_usages";
CREATE TABLE "public"."invite_code_usages" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "invite_code_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "used_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "ip_address" varchar(45) COLLATE "pg_catalog"."default",
  "user_agent" varchar(500) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for invite_codes
-- ----------------------------
DROP TABLE IF EXISTS "public"."invite_codes";
CREATE TABLE "public"."invite_codes" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "code" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "created_by" uuid NOT NULL,
  "max_uses" int4 NOT NULL DEFAULT 1,
  "used_count" int4 NOT NULL DEFAULT 0,
  "expires_at" timestamptz(6),
  "description" varchar(200) COLLATE "pg_catalog"."default",
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'member'::character varying,
  "is_active" bool NOT NULL DEFAULT true,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for knowledge_bases
-- ----------------------------
DROP TABLE IF EXISTS "public"."knowledge_bases";
CREATE TABLE "public"."knowledge_bases" (
  "id" uuid NOT NULL,
  "name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "created_at" timestamp(6),
  "user_id" uuid NOT NULL,
  "updated_at" timestamp(6),
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "visibility" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'private'::character varying
)
;

-- ----------------------------
-- Table structure for langgraph_checkpoints
-- ----------------------------
DROP TABLE IF EXISTS "public"."langgraph_checkpoints";
CREATE TABLE "public"."langgraph_checkpoints" (
  "thread_id" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "checkpoint_id" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "parent_checkpoint_id" varchar(255) COLLATE "pg_catalog"."default",
  "checkpoint_data" jsonb NOT NULL,
  "extra_metadata" jsonb,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Table structure for multi_agent_intent_analyses
-- ----------------------------
DROP TABLE IF EXISTS "public"."multi_agent_intent_analyses";
CREATE TABLE "public"."multi_agent_intent_analyses" (
  "id" uuid NOT NULL,
  "session_id" uuid NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "primary_intent" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "sub_intents" jsonb,
  "routing_strategy" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "required_specialists" jsonb,
  "complexity" varchar(20) COLLATE "pg_catalog"."default",
  "confidence" float8,
  "raw_query" text COLLATE "pg_catalog"."default",
  "interpreted_query" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for multi_agent_reflection_records
-- ----------------------------
DROP TABLE IF EXISTS "public"."multi_agent_reflection_records";
CREATE TABLE "public"."multi_agent_reflection_records" (
  "id" uuid NOT NULL,
  "session_id" uuid NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "quality_score" float8,
  "quality_level" varchar(20) COLLATE "pg_catalog"."default",
  "needs_revision" bool,
  "revision_reason" text COLLATE "pg_catalog"."default",
  "suggestions" jsonb,
  "improvement_summary" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for multi_agent_report_access_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."multi_agent_report_access_logs";
CREATE TABLE "public"."multi_agent_report_access_logs" (
  "id" uuid NOT NULL,
  "report_id" uuid NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" uuid,
  "action" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "access_type" varchar(20) COLLATE "pg_catalog"."default",
  "ip_address" varchar(50) COLLATE "pg_catalog"."default",
  "user_agent" varchar(500) COLLATE "pg_catalog"."default",
  "duration_ms" int4,
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for multi_agent_report_versions
-- ----------------------------
DROP TABLE IF EXISTS "public"."multi_agent_report_versions";
CREATE TABLE "public"."multi_agent_report_versions" (
  "id" uuid NOT NULL,
  "report_id" uuid NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "version" int4 NOT NULL,
  "content_snapshot" text COLLATE "pg_catalog"."default",
  "metadata_snapshot" jsonb,
  "change_reason" varchar(200) COLLATE "pg_catalog"."default",
  "changed_by" varchar(100) COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for multi_agent_reports
-- ----------------------------
DROP TABLE IF EXISTS "public"."multi_agent_reports";
CREATE TABLE "public"."multi_agent_reports" (
  "id" uuid NOT NULL,
  "session_id" uuid NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" uuid,
  "report_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "format" varchar(20) COLLATE "pg_catalog"."default",
  "title" varchar(500) COLLATE "pg_catalog"."default",
  "summary" text COLLATE "pg_catalog"."default",
  "content" text COLLATE "pg_catalog"."default",
  "sections" jsonb,
  "extra_metadata" jsonb,
  "version" int4,
  "is_latest" bool,
  "parent_report_id" uuid,
  "quality_score" float8,
  "quality_level" varchar(20) COLLATE "pg_catalog"."default",
  "generated_by" varchar(100) COLLATE "pg_catalog"."default",
  "generation_time" float8,
  "word_count" int4,
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for multi_agent_sessions
-- ----------------------------
DROP TABLE IF EXISTS "public"."multi_agent_sessions";
CREATE TABLE "public"."multi_agent_sessions" (
  "id" uuid NOT NULL,
  "session_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" uuid,
  "user_query" text COLLATE "pg_catalog"."default" NOT NULL,
  "primary_intent" varchar(50) COLLATE "pg_catalog"."default",
  "routing_strategy" varchar(50) COLLATE "pg_catalog"."default",
  "complexity" varchar(20) COLLATE "pg_catalog"."default",
  "enable_reflection" bool,
  "confidence_threshold" float8,
  "max_specialists" int4,
  "status" varchar(20) COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6),
  "completed_at" timestamptz(6),
  "extra_metadata" jsonb
)
;

-- ----------------------------
-- Table structure for multi_agent_specialist_results
-- ----------------------------
DROP TABLE IF EXISTS "public"."multi_agent_specialist_results";
CREATE TABLE "public"."multi_agent_specialist_results" (
  "id" uuid NOT NULL,
  "session_id" uuid NOT NULL,
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "specialist_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "specialist_name" varchar(100) COLLATE "pg_catalog"."default",
  "query" text COLLATE "pg_catalog"."default",
  "analysis" jsonb,
  "raw_response" text COLLATE "pg_catalog"."default",
  "confidence" float8,
  "processing_time" float8,
  "success" bool,
  "error_message" text COLLATE "pg_catalog"."default",
  "execution_order" int4,
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for policies
-- ----------------------------
DROP TABLE IF EXISTS "public"."policies";
CREATE TABLE "public"."policies" (
  "id" uuid NOT NULL,
  "policy_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default",
  "summary" varchar(2000) COLLATE "pg_catalog"."default",
  "source_name" varchar(100) COLLATE "pg_catalog"."default",
  "source_url" varchar(1000) COLLATE "pg_catalog"."default",
  "published_date" timestamptz(6),
  "effective_date" timestamptz(6),
  "expiry_date" timestamptz(6),
  "priority" varchar(20) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default",
  "industries" varchar(100)[] COLLATE "pg_catalog"."default",
  "regions" varchar(100)[] COLLATE "pg_catalog"."default",
  "scales" varchar(50)[] COLLATE "pg_catalog"."default",
  "tax_types" varchar(100)[] COLLATE "pg_catalog"."default",
  "tags" varchar(50)[] COLLATE "pg_catalog"."default",
  "meta_info" json,
  "view_count" int4,
  "created_at" timestamptz(6),
  "updated_at" timestamptz(6),
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default",
  "version" varchar(50) COLLATE "pg_catalog"."default" DEFAULT 1,
  "embedding" "public"."halfvec"
)
;

-- ----------------------------
-- Table structure for policy_relations
-- ----------------------------
DROP TABLE IF EXISTS "public"."policy_relations";
CREATE TABLE "public"."policy_relations" (
  "id" uuid NOT NULL,
  "source_policy_id" uuid NOT NULL,
  "target_policy_id" uuid NOT NULL,
  "relation_type" varchar(50) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6),
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for prompt_ab_tests
-- ----------------------------
DROP TABLE IF EXISTS "public"."prompt_ab_tests";
CREATE TABLE "public"."prompt_ab_tests" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "test_name" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "template_a_id" uuid,
  "template_b_id" uuid,
  "traffic_split" float8 DEFAULT 0.5,
  "status" varchar COLLATE "pg_catalog"."default" DEFAULT 'running'::character varying,
  "start_date" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "end_date" timestamptz(6),
  "total_executions" int4 DEFAULT 0,
  "winner_template_id" uuid,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for prompt_executions
-- ----------------------------
DROP TABLE IF EXISTS "public"."prompt_executions";
CREATE TABLE "public"."prompt_executions" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "template_id" uuid,
  "trace_id" uuid,
  "user_query" text COLLATE "pg_catalog"."default" NOT NULL,
  "final_answer" text COLLATE "pg_catalog"."default",
  "execution_time" float8,
  "iterations_count" int4,
  "tool_calls_count" int4,
  "success" bool NOT NULL,
  "user_feedback" int4,
  "auto_score" float8,
  "error_type" varchar COLLATE "pg_catalog"."default",
  "error_message" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Table structure for prompt_templates
-- ----------------------------
DROP TABLE IF EXISTS "public"."prompt_templates";
CREATE TABLE "public"."prompt_templates" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "name" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "version" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "template_text" text COLLATE "pg_catalog"."default" NOT NULL,
  "agent_type" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "use_case" varchar COLLATE "pg_catalog"."default" DEFAULT 'general'::character varying,
  "is_active" bool DEFAULT true,
  "is_baseline" bool DEFAULT false,
  "variables" jsonb,
  "description" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for review_request_actions
-- ----------------------------
DROP TABLE IF EXISTS "public"."review_request_actions";
CREATE TABLE "public"."review_request_actions" (
  "id" uuid NOT NULL,
  "review_request_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "action" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "action_details" jsonb,
  "old_value" jsonb,
  "new_value" jsonb,
  "ip_address" varchar(50) COLLATE "pg_catalog"."default",
  "user_agent" varchar(500) COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) NOT NULL DEFAULT now()
)
;
COMMENT ON COLUMN "public"."review_request_actions"."action" IS '操作类型: create/assign/approve/reject/comment/escalate';
COMMENT ON COLUMN "public"."review_request_actions"."action_details" IS '操作详情';
COMMENT ON COLUMN "public"."review_request_actions"."old_value" IS '旧值';
COMMENT ON COLUMN "public"."review_request_actions"."new_value" IS '新值';
COMMENT ON COLUMN "public"."review_request_actions"."ip_address" IS 'IP地址';
COMMENT ON COLUMN "public"."review_request_actions"."user_agent" IS 'User Agent';

-- ----------------------------
-- Table structure for review_request_comments
-- ----------------------------
DROP TABLE IF EXISTS "public"."review_request_comments";
CREATE TABLE "public"."review_request_comments" (
  "id" uuid NOT NULL,
  "review_request_id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "comment_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "related_entity_type" varchar(50) COLLATE "pg_catalog"."default",
  "related_entity_id" varchar(100) COLLATE "pg_catalog"."default",
  "attachments" jsonb,
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "updated_at" timestamptz(6) NOT NULL DEFAULT now()
)
;
COMMENT ON COLUMN "public"."review_request_comments"."content" IS '评论内容';
COMMENT ON COLUMN "public"."review_request_comments"."comment_type" IS '评论类型: comment/note/action';
COMMENT ON COLUMN "public"."review_request_comments"."related_entity_type" IS '关联实体类型';
COMMENT ON COLUMN "public"."review_request_comments"."related_entity_id" IS '关联实体ID';
COMMENT ON COLUMN "public"."review_request_comments"."attachments" IS '附件列表';

-- ----------------------------
-- Table structure for review_requests
-- ----------------------------
DROP TABLE IF EXISTS "public"."review_requests";
CREATE TABLE "public"."review_requests" (
  "id" uuid NOT NULL,
  "task_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" uuid NOT NULL,
  "review_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "priority" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "trigger_reason" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "trigger_details" jsonb,
  "title" varchar(500) COLLATE "pg_catalog"."default",
  "description" text COLLATE "pg_catalog"."default",
  "content" jsonb,
  "document_ids" jsonb,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "assigned_to" uuid,
  "assigned_at" timestamptz(6),
  "review_result" jsonb,
  "review_comments" text COLLATE "pg_catalog"."default",
  "reviewed_at" timestamptz(6),
  "reviewed_by" uuid,
  "processing_time_seconds" int4,
  "sla_deadline" timestamptz(6),
  "extra_metadata" jsonb,
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "updated_at" timestamptz(6) NOT NULL DEFAULT now()
)
;
COMMENT ON COLUMN "public"."review_requests"."task_id" IS '关联的任务ID';
COMMENT ON COLUMN "public"."review_requests"."tenant_id" IS '租户ID（隔离）';
COMMENT ON COLUMN "public"."review_requests"."user_id" IS '发起人ID';
COMMENT ON COLUMN "public"."review_requests"."review_type" IS '审核类型: tax/finance/legal/compliance';
COMMENT ON COLUMN "public"."review_requests"."priority" IS '优先级: low/normal/high/urgent';
COMMENT ON COLUMN "public"."review_requests"."trigger_reason" IS '触发原因';
COMMENT ON COLUMN "public"."review_requests"."trigger_details" IS '触发详情';
COMMENT ON COLUMN "public"."review_requests"."title" IS '审核标题';
COMMENT ON COLUMN "public"."review_requests"."description" IS '审核描述';
COMMENT ON COLUMN "public"."review_requests"."content" IS '审核内容（AI处理结果等）';
COMMENT ON COLUMN "public"."review_requests"."document_ids" IS '关联的文档ID列表';
COMMENT ON COLUMN "public"."review_requests"."status" IS '状态: pending/in_progress/completed/rejected';
COMMENT ON COLUMN "public"."review_requests"."assigned_to" IS '分配给谁';
COMMENT ON COLUMN "public"."review_requests"."assigned_at" IS '分配时间';
COMMENT ON COLUMN "public"."review_requests"."review_result" IS '审核结果';
COMMENT ON COLUMN "public"."review_requests"."review_comments" IS '审核意见';
COMMENT ON COLUMN "public"."review_requests"."reviewed_at" IS '审核时间';
COMMENT ON COLUMN "public"."review_requests"."reviewed_by" IS '审核人';
COMMENT ON COLUMN "public"."review_requests"."processing_time_seconds" IS '处理时长（秒）';
COMMENT ON COLUMN "public"."review_requests"."sla_deadline" IS 'SLA截止时间';
COMMENT ON COLUMN "public"."review_requests"."extra_metadata" IS '其他元数据';

-- ----------------------------
-- Table structure for scheduled_tasks
-- ----------------------------
DROP TABLE IF EXISTS "public"."scheduled_tasks";
CREATE TABLE "public"."scheduled_tasks" (
  "id" uuid NOT NULL,
  "task_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "task_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "frequency" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "next_run_time" timestamptz(6),
  "last_run_time" timestamptz(6),
  "task_params" jsonb,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "enabled" bool NOT NULL DEFAULT true,
  "retry_count" int4 NOT NULL DEFAULT 0,
  "max_retries" int4 NOT NULL DEFAULT 3,
  "notification_enabled" bool NOT NULL DEFAULT true,
  "notification_channels" jsonb,
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "updated_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for search_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."search_logs";
CREATE TABLE "public"."search_logs" (
  "id" uuid NOT NULL,
  "query" text COLLATE "pg_catalog"."default" NOT NULL,
  "result_count" int4,
  "latency" float8,
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for semantic_memories
-- ----------------------------
DROP TABLE IF EXISTS "public"."semantic_memories";
CREATE TABLE "public"."semantic_memories" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "user_id" uuid NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "role" varchar(50) COLLATE "pg_catalog"."default" DEFAULT 'user'::character varying,
  "importance" float8 DEFAULT 0.5,
  "access_count" int4 DEFAULT 0,
  "decay_factor" float8 DEFAULT 1.0,
  "memory_type" varchar(50) COLLATE "pg_catalog"."default" DEFAULT 'general'::character varying,
  "tags" text[] COLLATE "pg_catalog"."default",
  "memory_metadata" jsonb,
  "source_session_id" uuid,
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "last_accessed" timestamptz(6) DEFAULT now(),
  "embedding" "public"."vector"
)
;

-- ----------------------------
-- Table structure for system_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."system_logs";
CREATE TABLE "public"."system_logs" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "created_at" timestamptz(6) DEFAULT now(),
  "level" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "category" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "action" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "message" text COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" uuid,
  "session_id" varchar(100) COLLATE "pg_catalog"."default",
  "request_id" varchar(100) COLLATE "pg_catalog"."default",
  "module" varchar(100) COLLATE "pg_catalog"."default",
  "function" varchar(100) COLLATE "pg_catalog"."default",
  "line_number" int4,
  "ip_address" varchar(45) COLLATE "pg_catalog"."default",
  "user_agent" text COLLATE "pg_catalog"."default",
  "endpoint" varchar(200) COLLATE "pg_catalog"."default",
  "method" varchar(10) COLLATE "pg_catalog"."default",
  "status_code" int4,
  "execution_time" int4,
  "memory_usage" int4,
  "extra_data" jsonb,
  "error_type" varchar(100) COLLATE "pg_catalog"."default",
  "error_message" text COLLATE "pg_catalog"."default",
  "stack_trace" text COLLATE "pg_catalog"."default",
  "is_sensitive" bool DEFAULT false,
  "is_archived" bool DEFAULT false,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for system_settings
-- ----------------------------
DROP TABLE IF EXISTS "public"."system_settings";
CREATE TABLE "public"."system_settings" (
  "key" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "value" jsonb,
  "updated_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for task_execution_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."task_execution_logs";
CREATE TABLE "public"."task_execution_logs" (
  "id" uuid NOT NULL,
  "task_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "scheduled_task_id" uuid,
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "task_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "start_time" timestamptz(6) NOT NULL,
  "end_time" timestamptz(6),
  "duration_seconds" int4,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "result" jsonb,
  "error_message" text COLLATE "pg_catalog"."default",
  "error_traceback" text COLLATE "pg_catalog"."default",
  "execution_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'scheduled'::character varying,
  "triggered_manually" bool NOT NULL DEFAULT false,
  "created_at" timestamptz(6) NOT NULL DEFAULT now()
)
;

-- ----------------------------
-- Table structure for task_notifications
-- ----------------------------
DROP TABLE IF EXISTS "public"."task_notifications";
CREATE TABLE "public"."task_notifications" (
  "id" uuid NOT NULL,
  "task_id" uuid,
  "execution_log_id" uuid,
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "notification_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "message" text COLLATE "pg_catalog"."default" NOT NULL,
  "channels" jsonb,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "sent_at" timestamptz(6),
  "created_at" timestamptz(6) NOT NULL DEFAULT now()
)
;

-- ----------------------------
-- Table structure for tax_report_documents
-- ----------------------------
DROP TABLE IF EXISTS "public"."tax_report_documents";
CREATE TABLE "public"."tax_report_documents" (
  "id" uuid NOT NULL,
  "tax_report_id" uuid NOT NULL,
  "filename" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "file_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "file_size" int8 NOT NULL,
  "minio_path" varchar(1000) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default",
  "processing_message" varchar(500) COLLATE "pg_catalog"."default",
  "extracted_content" text COLLATE "pg_catalog"."default",
  "ocr_result" jsonb,
  "created_at" timestamptz(6) DEFAULT now(),
  "processed_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for tax_reports
-- ----------------------------
DROP TABLE IF EXISTS "public"."tax_reports";
CREATE TABLE "public"."tax_reports" (
  "id" uuid NOT NULL,
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "audit_task_id" uuid,
  "filename" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "original_filename" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "file_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "file_size" int8 NOT NULL,
  "minio_path" varchar(1000) COLLATE "pg_catalog"."default" NOT NULL,
  "extracted_content" text COLLATE "pg_catalog"."default",
  "tax_type" varchar(50) COLLATE "pg_catalog"."default",
  "tax_period_year" int4,
  "tax_period_month" int4,
  "status" varchar(20) COLLATE "pg_catalog"."default",
  "processing_message" varchar(500) COLLATE "pg_catalog"."default",
  "processing_result" jsonb,
  "tax_validation_result" jsonb,
  "confidence_score" varchar(10) COLLATE "pg_catalog"."default",
  "risk_score" int4,
  "risk_level" varchar(20) COLLATE "pg_catalog"."default",
  "needs_human_review" varchar(5) COLLATE "pg_catalog"."default",
  "review_request_id" uuid,
  "pii_anonymized" varchar(5) COLLATE "pg_catalog"."default",
  "pii_mapping" jsonb,
  "key_metrics" jsonb,
  "issues_summary" jsonb,
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6),
  "completed_at" timestamptz(6),
  "expires_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for tenant_audit_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."tenant_audit_logs";
CREATE TABLE "public"."tenant_audit_logs" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "user_id" uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default",
  "action" varchar(100) COLLATE "pg_catalog"."default",
  "resource_type" varchar(50) COLLATE "pg_catalog"."default",
  "resource_id" varchar(100) COLLATE "pg_catalog"."default",
  "access_result" varchar(20) COLLATE "pg_catalog"."default",
  "ip_address" varchar(50) COLLATE "pg_catalog"."default",
  "user_agent" text COLLATE "pg_catalog"."default",
  "details" jsonb,
  "created_at" timestamptz(6) DEFAULT now(),
  "table_name" varchar(100) COLLATE "pg_catalog"."default",
  "record_id" varchar(100) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for tenant_settings
-- ----------------------------
DROP TABLE IF EXISTS "public"."tenant_settings";
CREATE TABLE "public"."tenant_settings" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "company_name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "company_logo" varchar(500) COLLATE "pg_catalog"."default",
  "company_description" text COLLATE "pg_catalog"."default",
  "company_website" varchar(500) COLLATE "pg_catalog"."default",
  "company_address" varchar(500) COLLATE "pg_catalog"."default",
  "company_phone" varchar(50) COLLATE "pg_catalog"."default",
  "company_email" varchar(255) COLLATE "pg_catalog"."default",
  "admin_name" varchar(100) COLLATE "pg_catalog"."default",
  "admin_email" varchar(255) COLLATE "pg_catalog"."default",
  "admin_phone" varchar(50) COLLATE "pg_catalog"."default",
  "industry" varchar(100) COLLATE "pg_catalog"."default",
  "region" varchar(100) COLLATE "pg_catalog"."default",
  "scale" varchar(50) COLLATE "pg_catalog"."default",
  "tax_types" varchar(100)[] COLLATE "pg_catalog"."default" DEFAULT '{}'::character varying[],
  "max_users" int4 DEFAULT 10,
  "max_storage_gb" int4 DEFAULT 100,
  "max_knowledge_bases" int4 DEFAULT 10,
  "max_documents" int4 DEFAULT 1000,
  "max_monthly_requests" int4,
  "enable_group_chat" bool DEFAULT true,
  "enable_multi_agent" bool DEFAULT true,
  "enable_knowledge_graph" bool DEFAULT false,
  "enable_human_review" bool DEFAULT true,
  "enable_audit" bool DEFAULT false,
  "enable_tax_report" bool DEFAULT false,
  "enable_financial_data" bool DEFAULT false,
  "primary_color" varchar(20) COLLATE "pg_catalog"."default" DEFAULT '#1890ff'::character varying,
  "secondary_color" varchar(20) COLLATE "pg_catalog"."default",
  "custom_css" text COLLATE "pg_catalog"."default",
  "custom_footer" text COLLATE "pg_catalog"."default",
  "email_notification" bool DEFAULT true,
  "system_notification" bool DEFAULT true,
  "notification_email" varchar(255) COLLATE "pg_catalog"."default",
  "is_active" bool DEFAULT true,
  "is_trial" bool DEFAULT true,
  "trial_expires_at" timestamptz(6),
  "extra_settings" jsonb
)
;

-- ----------------------------
-- Table structure for tool_call_traces
-- ----------------------------
DROP TABLE IF EXISTS "public"."tool_call_traces";
CREATE TABLE "public"."tool_call_traces" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "trace_id" uuid,
  "parent_call_id" uuid,
  "tool_name" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "tool_type" varchar COLLATE "pg_catalog"."default" DEFAULT 'function'::character varying,
  "input_params" jsonb,
  "output_result" text COLLATE "pg_catalog"."default",
  "start_time" float8 NOT NULL,
  "end_time" float8,
  "duration" float8,
  "status" varchar COLLATE "pg_catalog"."default" DEFAULT 'running'::character varying,
  "error_message" text COLLATE "pg_catalog"."default",
  "metadata" jsonb,
  "created_at" timestamptz(6) DEFAULT CURRENT_TIMESTAMP,
  "tool_metadata" json,
  "user_id" uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default",
  "session_id" uuid
)
;

-- ----------------------------
-- Table structure for update_history
-- ----------------------------
DROP TABLE IF EXISTS "public"."update_history";
CREATE TABLE "public"."update_history" (
  "id" uuid NOT NULL,
  "source_name" varchar(100) COLLATE "pg_catalog"."default",
  "update_type" varchar(50) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default",
  "policies_added" int4,
  "policies_updated" int4,
  "error_message" text COLLATE "pg_catalog"."default",
  "started_at" timestamp(6),
  "completed_at" timestamp(6),
  "tenant_id" varchar(100) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for user_action_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_action_logs";
CREATE TABLE "public"."user_action_logs" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "created_at" timestamptz(6) DEFAULT now(),
  "user_id" uuid,
  "user_email" varchar(255) COLLATE "pg_catalog"."default",
  "action_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "action_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "resource_type" varchar(50) COLLATE "pg_catalog"."default",
  "resource_id" varchar(100) COLLATE "pg_catalog"."default",
  "resource_name" varchar(200) COLLATE "pg_catalog"."default",
  "success" bool NOT NULL DEFAULT true,
  "result_message" text COLLATE "pg_catalog"."default",
  "ip_address" varchar(45) COLLATE "pg_catalog"."default",
  "user_agent" text COLLATE "pg_catalog"."default",
  "session_id" varchar(100) COLLATE "pg_catalog"."default",
  "before_data" jsonb,
  "after_data" jsonb,
  "extra_info" jsonb,
  "level" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'INFO'::character varying,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default",
  "risk_level" varchar(20) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Table structure for user_feedback
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_feedback";
CREATE TABLE "public"."user_feedback" (
  "id" uuid NOT NULL,
  "session_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "message_id" uuid,
  "user_id" uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default",
  "query" text COLLATE "pg_catalog"."default" NOT NULL,
  "response" text COLLATE "pg_catalog"."default" NOT NULL,
  "feedback_type" "public"."feedback_type_enum" NOT NULL,
  "rating" int4,
  "comment" text COLLATE "pg_catalog"."default",
  "retrieval_method" varchar(50) COLLATE "pg_catalog"."default",
  "chunks_used" jsonb,
  "kb_id" varchar(100) COLLATE "pg_catalog"."default",
  "retrieval_time" int4,
  "generation_time" int4,
  "total_time" int4,
  "token_count" int4,
  "created_at" timestamptz(6) DEFAULT now()
)
;
COMMENT ON COLUMN "public"."user_feedback"."session_id" IS '会话 ID';
COMMENT ON COLUMN "public"."user_feedback"."message_id" IS '消息 ID';
COMMENT ON COLUMN "public"."user_feedback"."query" IS '用户查询';
COMMENT ON COLUMN "public"."user_feedback"."response" IS '系统响应';
COMMENT ON COLUMN "public"."user_feedback"."feedback_type" IS '反馈类型';
COMMENT ON COLUMN "public"."user_feedback"."rating" IS '评分 1-5';
COMMENT ON COLUMN "public"."user_feedback"."comment" IS '用户评论';
COMMENT ON COLUMN "public"."user_feedback"."retrieval_method" IS '检索方法 (simple/graphrag/agentic)';
COMMENT ON COLUMN "public"."user_feedback"."chunks_used" IS '使用的文档块';
COMMENT ON COLUMN "public"."user_feedback"."kb_id" IS '知识库 ID';
COMMENT ON COLUMN "public"."user_feedback"."retrieval_time" IS '检索时间(ms)';
COMMENT ON COLUMN "public"."user_feedback"."generation_time" IS '生成时间(ms)';
COMMENT ON COLUMN "public"."user_feedback"."total_time" IS '总时间(ms)';
COMMENT ON COLUMN "public"."user_feedback"."token_count" IS 'Token 消耗';

-- ----------------------------
-- Table structure for user_financial_data
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_financial_data";
CREATE TABLE "public"."user_financial_data" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "user_id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "fiscal_year" int4 NOT NULL,
  "total_revenue" float8 DEFAULT 0,
  "taxable_sales" float8 DEFAULT 0,
  "tax_free_sales" float8 DEFAULT 0,
  "total_expenses" float8 DEFAULT 0,
  "deductible_expenses" float8 DEFAULT 0,
  "non_deductible_expenses" float8 DEFAULT 0,
  "input_tax" float8 DEFAULT 0,
  "output_tax" float8 DEFAULT 0,
  "vat_rate" float8 DEFAULT 0.13,
  "taxable_income" float8 DEFAULT 0,
  "corporate_tax_rate" float8 DEFAULT 0.25,
  "is_small_enterprise" bool DEFAULT false,
  "total_payroll" float8 DEFAULT 0,
  "special_deductions" float8 DEFAULT 0,
  "cost_breakdown" jsonb,
  "total_invoices" int4 DEFAULT 0,
  "input_invoice_count" int4 DEFAULT 0,
  "output_invoice_count" int4 DEFAULT 0,
  "data_status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'draft'::character varying,
  "is_current" bool DEFAULT true,
  "data_source" varchar(50) COLLATE "pg_catalog"."default" DEFAULT 'manual'::character varying,
  "source_file_id" uuid,
  "notes" text COLLATE "pg_catalog"."default",
  "reviewed_by" uuid,
  "reviewed_at" timestamptz(6),
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6) DEFAULT now(),
  "period_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'yearly'::character varying,
  "period_start" date NOT NULL DEFAULT '2024-01-01'::date,
  "period_end" date NOT NULL DEFAULT '2024-12-31'::date,
  "tax_period" varchar(50) COLLATE "pg_catalog"."default",
  "deductions" jsonb,
  "exemptions" jsonb
)
;

-- ----------------------------
-- Table structure for user_multimodal_configs
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_multimodal_configs";
CREATE TABLE "public"."user_multimodal_configs" (
  "id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "enabled" bool NOT NULL,
  "table_mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "chart_mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "image_mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "vision_model" varchar(50) COLLATE "pg_catalog"."default",
  "llm_model" varchar(50) COLLATE "pg_catalog"."default",
  "user_api_key_encrypted" varchar(500) COLLATE "pg_catalog"."default",
  "use_own_api_key" bool NOT NULL,
  "daily_ai_limit" int4 NOT NULL,
  "daily_ai_used" int4 NOT NULL,
  "last_reset_at" timestamptz(6) NOT NULL,
  "total_ai_calls" int4 NOT NULL,
  "enable_cache" bool NOT NULL,
  "ai_timeout" int4 NOT NULL,
  "max_concurrent" int4 NOT NULL,
  "custom_config" jsonb NOT NULL,
  "created_at" timestamptz(6) DEFAULT now(),
  "updated_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for user_multimodal_usage_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_multimodal_usage_logs";
CREATE TABLE "public"."user_multimodal_usage_logs" (
  "id" uuid NOT NULL,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" uuid,
  "document_id" uuid,
  "content_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "parse_mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "model_used" varchar(50) COLLATE "pg_catalog"."default",
  "input_tokens" int4,
  "output_tokens" int4,
  "total_tokens" int4,
  "estimated_cost" varchar(20) COLLATE "pg_catalog"."default",
  "response_time_ms" int4,
  "success" bool,
  "error_message" varchar(500) COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS "public"."users";
CREATE TABLE "public"."users" (
  "id" uuid NOT NULL,
  "email" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "full_name" varchar(100) COLLATE "pg_catalog"."default",
  "hashed_password" varchar COLLATE "pg_catalog"."default" NOT NULL,
  "is_active" bool,
  "created_at" timestamptz(6) DEFAULT now(),
  "avatar_url" varchar COLLATE "pg_catalog"."default",
  "is_admin" bool DEFAULT false,
  "phone" varchar(20) COLLATE "pg_catalog"."default",
  "nickname" varchar(50) COLLATE "pg_catalog"."default",
  "bio" text COLLATE "pg_catalog"."default",
  "company_name" varchar(200) COLLATE "pg_catalog"."default",
  "company_position" varchar(100) COLLATE "pg_catalog"."default",
  "is_phone_verified" bool DEFAULT false,
  "updated_at" timestamptz(6) DEFAULT now(),
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "username" varchar(50) COLLATE "pg_catalog"."default",
  "managed_tenant_ids" text COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for workflow_node_executions
-- ----------------------------
DROP TABLE IF EXISTS "public"."workflow_node_executions";
CREATE TABLE "public"."workflow_node_executions" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "workflow_trace_id" uuid NOT NULL,
  "agent_trace_id" uuid,
  "node_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "node_type" varchar(50) COLLATE "pg_catalog"."default",
  "execution_order" int4 NOT NULL DEFAULT 0,
  "input_data" jsonb,
  "output_data" jsonb,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'running'::character varying,
  "error_message" text COLLATE "pg_catalog"."default",
  "execution_time_ms" float8,
  "token_usage" jsonb,
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "completed_at" timestamptz(6)
)
;

-- ----------------------------
-- Table structure for workflow_traces
-- ----------------------------
DROP TABLE IF EXISTS "public"."workflow_traces";
CREATE TABLE "public"."workflow_traces" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "workflow_type" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "workflow_version" varchar(50) COLLATE "pg_catalog"."default",
  "session_id" uuid,
  "tenant_id" varchar(50) COLLATE "pg_catalog"."default",
  "user_id" uuid,
  "input_data" jsonb,
  "output_data" jsonb,
  "status" varchar(30) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "current_node" varchar(100) COLLATE "pg_catalog"."default",
  "total_nodes" int4 NOT NULL DEFAULT 0,
  "completed_nodes" int4 NOT NULL DEFAULT 0,
  "execution_time_ms" float8,
  "error_message" text COLLATE "pg_catalog"."default",
  "checkpointer_type" varchar(20) COLLATE "pg_catalog"."default",
  "checkpoint_id" varchar(100) COLLATE "pg_catalog"."default",
  "workflow_metadata" jsonb,
  "human_review_id" uuid,
  "created_at" timestamptz(6) NOT NULL DEFAULT now(),
  "updated_at" timestamptz(6) NOT NULL DEFAULT now(),
  "completed_at" timestamptz(6)
)
;

-- ----------------------------
-- Function structure for armor
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."armor"(bytea);
CREATE FUNCTION "public"."armor"(bytea)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pg_armor'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for armor
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."armor"(bytea, _text, _text);
CREATE FUNCTION "public"."armor"(bytea, _text, _text)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pg_armor'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_halfvec"(_numeric, int4, bool);
CREATE FUNCTION "public"."array_to_halfvec"(_numeric, int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'array_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_halfvec"(_int4, int4, bool);
CREATE FUNCTION "public"."array_to_halfvec"(_int4, int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'array_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_halfvec"(_float4, int4, bool);
CREATE FUNCTION "public"."array_to_halfvec"(_float4, int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'array_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_halfvec"(_float8, int4, bool);
CREATE FUNCTION "public"."array_to_halfvec"(_float8, int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'array_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_sparsevec"(_float8, int4, bool);
CREATE FUNCTION "public"."array_to_sparsevec"(_float8, int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'array_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_sparsevec"(_numeric, int4, bool);
CREATE FUNCTION "public"."array_to_sparsevec"(_numeric, int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'array_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_sparsevec"(_int4, int4, bool);
CREATE FUNCTION "public"."array_to_sparsevec"(_int4, int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'array_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_sparsevec"(_float4, int4, bool);
CREATE FUNCTION "public"."array_to_sparsevec"(_float4, int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'array_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_vector"(_float8, int4, bool);
CREATE FUNCTION "public"."array_to_vector"(_float8, int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'array_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_vector"(_int4, int4, bool);
CREATE FUNCTION "public"."array_to_vector"(_int4, int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'array_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_vector"(_float4, int4, bool);
CREATE FUNCTION "public"."array_to_vector"(_float4, int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'array_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for array_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."array_to_vector"(_numeric, int4, bool);
CREATE FUNCTION "public"."array_to_vector"(_numeric, int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'array_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for binary_quantize
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."binary_quantize"("public"."vector");
CREATE FUNCTION "public"."binary_quantize"("public"."vector")
  RETURNS "pg_catalog"."bit" AS '$libdir/vector', 'binary_quantize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for binary_quantize
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."binary_quantize"("public"."halfvec");
CREATE FUNCTION "public"."binary_quantize"("public"."halfvec")
  RETURNS "pg_catalog"."bit" AS '$libdir/vector', 'halfvec_binary_quantize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for cosine_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."cosine_distance"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."cosine_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_cosine_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for cosine_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."cosine_distance"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."cosine_distance"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_cosine_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for cosine_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."cosine_distance"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."cosine_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'cosine_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for crypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."crypt"(text, text);
CREATE FUNCTION "public"."crypt"(text, text)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pg_crypt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for dearmor
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."dearmor"(text);
CREATE FUNCTION "public"."dearmor"(text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_dearmor'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for decrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."decrypt"(bytea, bytea, text);
CREATE FUNCTION "public"."decrypt"(bytea, bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_decrypt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for decrypt_iv
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."decrypt_iv"(bytea, bytea, bytea, text);
CREATE FUNCTION "public"."decrypt_iv"(bytea, bytea, bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_decrypt_iv'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for digest
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."digest"(text, text);
CREATE FUNCTION "public"."digest"(text, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_digest'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for digest
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."digest"(bytea, text);
CREATE FUNCTION "public"."digest"(bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_digest'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for encrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."encrypt"(bytea, bytea, text);
CREATE FUNCTION "public"."encrypt"(bytea, bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_encrypt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for encrypt_iv
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."encrypt_iv"(bytea, bytea, bytea, text);
CREATE FUNCTION "public"."encrypt_iv"(bytea, bytea, bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_encrypt_iv'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gen_random_bytes
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."gen_random_bytes"(int4);
CREATE FUNCTION "public"."gen_random_bytes"(int4)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_random_bytes'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gen_random_uuid
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."gen_random_uuid"();
CREATE FUNCTION "public"."gen_random_uuid"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/pgcrypto', 'pg_random_uuid'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for gen_salt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."gen_salt"(text, int4);
CREATE FUNCTION "public"."gen_salt"(text, int4)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pg_gen_salt_rounds'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for gen_salt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."gen_salt"(text);
CREATE FUNCTION "public"."gen_salt"(text)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pg_gen_salt'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec"("public"."halfvec", int4, bool);
CREATE FUNCTION "public"."halfvec"("public"."halfvec", int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_accum
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_accum"(_float8, "public"."halfvec");
CREATE FUNCTION "public"."halfvec_accum"(_float8, "public"."halfvec")
  RETURNS "pg_catalog"."_float8" AS '$libdir/vector', 'halfvec_accum'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_add
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_add"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_add"("public"."halfvec", "public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_add'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_avg
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_avg"(_float8);
CREATE FUNCTION "public"."halfvec_avg"(_float8)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_avg'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_cmp
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_cmp"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_cmp"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'halfvec_cmp'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_combine
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_combine"(_float8, _float8);
CREATE FUNCTION "public"."halfvec_combine"(_float8, _float8)
  RETURNS "pg_catalog"."_float8" AS '$libdir/vector', 'vector_combine'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_concat
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_concat"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_concat"("public"."halfvec", "public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_concat'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_eq
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_eq"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_eq"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_eq'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_ge
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_ge"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_ge"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_ge'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_gt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_gt"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_gt"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_gt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_in
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_in"(cstring, oid, int4);
CREATE FUNCTION "public"."halfvec_in"(cstring, oid, int4)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_l2_squared_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_l2_squared_distance"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_l2_squared_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_l2_squared_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_le
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_le"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_le"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_le'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_lt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_lt"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_lt"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_lt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_mul
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_mul"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_mul"("public"."halfvec", "public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_mul'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_ne
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_ne"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_ne"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'halfvec_ne'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_negative_inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_negative_inner_product"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_negative_inner_product"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_negative_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_out
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_out"("public"."halfvec");
CREATE FUNCTION "public"."halfvec_out"("public"."halfvec")
  RETURNS "pg_catalog"."cstring" AS '$libdir/vector', 'halfvec_out'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_recv
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_recv"(internal, oid, int4);
CREATE FUNCTION "public"."halfvec_recv"(internal, oid, int4)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_recv'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_send
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_send"("public"."halfvec");
CREATE FUNCTION "public"."halfvec_send"("public"."halfvec")
  RETURNS "pg_catalog"."bytea" AS '$libdir/vector', 'halfvec_send'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_spherical_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_spherical_distance"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_spherical_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_spherical_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_sub
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_sub"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."halfvec_sub"("public"."halfvec", "public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_sub'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_to_float4
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_to_float4"("public"."halfvec", int4, bool);
CREATE FUNCTION "public"."halfvec_to_float4"("public"."halfvec", int4, bool)
  RETURNS "pg_catalog"."_float4" AS '$libdir/vector', 'halfvec_to_float4'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_to_sparsevec"("public"."halfvec", int4, bool);
CREATE FUNCTION "public"."halfvec_to_sparsevec"("public"."halfvec", int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'halfvec_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_to_vector"("public"."halfvec", int4, bool);
CREATE FUNCTION "public"."halfvec_to_vector"("public"."halfvec", int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'halfvec_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for halfvec_typmod_in
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."halfvec_typmod_in"(_cstring);
CREATE FUNCTION "public"."halfvec_typmod_in"(_cstring)
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'halfvec_typmod_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for hamming_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."hamming_distance"(bit, bit);
CREATE FUNCTION "public"."hamming_distance"(bit, bit)
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'hamming_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for hmac
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."hmac"(text, text, text);
CREATE FUNCTION "public"."hmac"(text, text, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_hmac'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for hmac
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."hmac"(bytea, bytea, text);
CREATE FUNCTION "public"."hmac"(bytea, bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pg_hmac'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for hnsw_bit_support
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."hnsw_bit_support"(internal);
CREATE FUNCTION "public"."hnsw_bit_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'hnsw_bit_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for hnsw_halfvec_support
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."hnsw_halfvec_support"(internal);
CREATE FUNCTION "public"."hnsw_halfvec_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'hnsw_halfvec_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for hnsw_sparsevec_support
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."hnsw_sparsevec_support"(internal);
CREATE FUNCTION "public"."hnsw_sparsevec_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'hnsw_sparsevec_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for hnswhandler
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."hnswhandler"(internal);
CREATE FUNCTION "public"."hnswhandler"(internal)
  RETURNS "pg_catalog"."index_am_handler" AS '$libdir/vector', 'hnswhandler'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."inner_product"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."inner_product"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."inner_product"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."inner_product"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."inner_product"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."inner_product"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for ivfflat_bit_support
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."ivfflat_bit_support"(internal);
CREATE FUNCTION "public"."ivfflat_bit_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'ivfflat_bit_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for ivfflat_halfvec_support
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."ivfflat_halfvec_support"(internal);
CREATE FUNCTION "public"."ivfflat_halfvec_support"(internal)
  RETURNS "pg_catalog"."internal" AS '$libdir/vector', 'ivfflat_halfvec_support'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for ivfflathandler
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."ivfflathandler"(internal);
CREATE FUNCTION "public"."ivfflathandler"(internal)
  RETURNS "pg_catalog"."index_am_handler" AS '$libdir/vector', 'ivfflathandler'
  LANGUAGE c VOLATILE
  COST 1;

-- ----------------------------
-- Function structure for jaccard_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."jaccard_distance"(bit, bit);
CREATE FUNCTION "public"."jaccard_distance"(bit, bit)
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'jaccard_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l1_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l1_distance"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."l1_distance"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_l1_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l1_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l1_distance"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."l1_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'l1_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l1_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l1_distance"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."l1_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_l1_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l2_distance"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."l2_distance"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_l2_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l2_distance"("public"."halfvec", "public"."halfvec");
CREATE FUNCTION "public"."l2_distance"("public"."halfvec", "public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_l2_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l2_distance"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."l2_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'l2_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_norm
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l2_norm"("public"."sparsevec");
CREATE FUNCTION "public"."l2_norm"("public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_l2_norm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_norm
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l2_norm"("public"."halfvec");
CREATE FUNCTION "public"."l2_norm"("public"."halfvec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'halfvec_l2_norm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_normalize
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l2_normalize"("public"."sparsevec");
CREATE FUNCTION "public"."l2_normalize"("public"."sparsevec")
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'sparsevec_l2_normalize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_normalize
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l2_normalize"("public"."vector");
CREATE FUNCTION "public"."l2_normalize"("public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'l2_normalize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for l2_normalize
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."l2_normalize"("public"."halfvec");
CREATE FUNCTION "public"."l2_normalize"("public"."halfvec")
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_l2_normalize'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for log_tenant_access
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."log_tenant_access"();
CREATE FUNCTION "public"."log_tenant_access"()
  RETURNS "pg_catalog"."trigger" AS $BODY$
            BEGIN
                INSERT INTO tenant_audit_logs (
                    tenant_id,
                    user_id,
                    action,
                    table_name,
                    record_id,
                    details,
                    created_at
                ) VALUES (
                    COALESCE(
                        CASE 
                            WHEN TG_OP = 'DELETE' THEN OLD.tenant_id
                            ELSE NEW.tenant_id
                        END,
                        'UNKNOWN'
                    ),
                    CASE 
                        WHEN current_setting('app.current_user_id', true) != '' 
                        THEN current_setting('app.current_user_id', true)::UUID
                        ELSE NULL
                    END,
                    TG_OP,
                    TG_TABLE_NAME,
                    CASE 
                        WHEN TG_OP = 'DELETE' THEN OLD.id::text
                        ELSE NEW.id::text
                    END,
                    jsonb_build_object(
                        'operation', TG_OP,
                        'table', TG_TABLE_NAME,
                        'ip_address', inet_client_addr()::text,
                        'timestamp', NOW()
                    ),
                    NOW()
                );
                
                RETURN CASE 
                    WHEN TG_OP = 'DELETE' THEN OLD
                    ELSE NEW
                END;
            END;
            $BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;

-- ----------------------------
-- Function structure for pgp_armor_headers
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_armor_headers"(text, OUT "key" text, OUT "value" text);
CREATE FUNCTION "public"."pgp_armor_headers"(IN text, OUT "key" text, OUT "value" text)
  RETURNS SETOF "pg_catalog"."record" AS '$libdir/pgcrypto', 'pgp_armor_headers'
  LANGUAGE c IMMUTABLE STRICT
  COST 1
  ROWS 1000;

-- ----------------------------
-- Function structure for pgp_key_id
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_key_id"(bytea);
CREATE FUNCTION "public"."pgp_key_id"(bytea)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pgp_key_id_w'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_decrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_decrypt"(bytea, bytea);
CREATE FUNCTION "public"."pgp_pub_decrypt"(bytea, bytea)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pgp_pub_decrypt_text'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_decrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_decrypt"(bytea, bytea, text);
CREATE FUNCTION "public"."pgp_pub_decrypt"(bytea, bytea, text)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pgp_pub_decrypt_text'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_decrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_decrypt"(bytea, bytea, text, text);
CREATE FUNCTION "public"."pgp_pub_decrypt"(bytea, bytea, text, text)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pgp_pub_decrypt_text'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_decrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_decrypt_bytea"(bytea, bytea, text);
CREATE FUNCTION "public"."pgp_pub_decrypt_bytea"(bytea, bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_pub_decrypt_bytea'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_decrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_decrypt_bytea"(bytea, bytea, text, text);
CREATE FUNCTION "public"."pgp_pub_decrypt_bytea"(bytea, bytea, text, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_pub_decrypt_bytea'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_decrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_decrypt_bytea"(bytea, bytea);
CREATE FUNCTION "public"."pgp_pub_decrypt_bytea"(bytea, bytea)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_pub_decrypt_bytea'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_encrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_encrypt"(text, bytea);
CREATE FUNCTION "public"."pgp_pub_encrypt"(text, bytea)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_pub_encrypt_text'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_encrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_encrypt"(text, bytea, text);
CREATE FUNCTION "public"."pgp_pub_encrypt"(text, bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_pub_encrypt_text'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_encrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_encrypt_bytea"(bytea, bytea);
CREATE FUNCTION "public"."pgp_pub_encrypt_bytea"(bytea, bytea)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_pub_encrypt_bytea'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_pub_encrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_pub_encrypt_bytea"(bytea, bytea, text);
CREATE FUNCTION "public"."pgp_pub_encrypt_bytea"(bytea, bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_pub_encrypt_bytea'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_sym_decrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_sym_decrypt"(bytea, text, text);
CREATE FUNCTION "public"."pgp_sym_decrypt"(bytea, text, text)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pgp_sym_decrypt_text'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_sym_decrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_sym_decrypt"(bytea, text);
CREATE FUNCTION "public"."pgp_sym_decrypt"(bytea, text)
  RETURNS "pg_catalog"."text" AS '$libdir/pgcrypto', 'pgp_sym_decrypt_text'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_sym_decrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_sym_decrypt_bytea"(bytea, text);
CREATE FUNCTION "public"."pgp_sym_decrypt_bytea"(bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_sym_decrypt_bytea'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_sym_decrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_sym_decrypt_bytea"(bytea, text, text);
CREATE FUNCTION "public"."pgp_sym_decrypt_bytea"(bytea, text, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_sym_decrypt_bytea'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_sym_encrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_sym_encrypt"(text, text);
CREATE FUNCTION "public"."pgp_sym_encrypt"(text, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_sym_encrypt_text'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_sym_encrypt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_sym_encrypt"(text, text, text);
CREATE FUNCTION "public"."pgp_sym_encrypt"(text, text, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_sym_encrypt_text'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_sym_encrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_sym_encrypt_bytea"(bytea, text, text);
CREATE FUNCTION "public"."pgp_sym_encrypt_bytea"(bytea, text, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_sym_encrypt_bytea'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for pgp_sym_encrypt_bytea
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."pgp_sym_encrypt_bytea"(bytea, text);
CREATE FUNCTION "public"."pgp_sym_encrypt_bytea"(bytea, text)
  RETURNS "pg_catalog"."bytea" AS '$libdir/pgcrypto', 'pgp_sym_encrypt_bytea'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec"("public"."sparsevec", int4, bool);
CREATE FUNCTION "public"."sparsevec"("public"."sparsevec", int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_cmp
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_cmp"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_cmp"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'sparsevec_cmp'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_eq
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_eq"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_eq"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_eq'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_ge
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_ge"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_ge"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_ge'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_gt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_gt"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_gt"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_gt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_in
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_in"(cstring, oid, int4);
CREATE FUNCTION "public"."sparsevec_in"(cstring, oid, int4)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'sparsevec_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_l2_squared_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_l2_squared_distance"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_l2_squared_distance"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_l2_squared_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_le
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_le"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_le"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_le'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_lt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_lt"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_lt"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_lt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_ne
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_ne"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_ne"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'sparsevec_ne'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_negative_inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_negative_inner_product"("public"."sparsevec", "public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_negative_inner_product"("public"."sparsevec", "public"."sparsevec")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'sparsevec_negative_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_out
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_out"("public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_out"("public"."sparsevec")
  RETURNS "pg_catalog"."cstring" AS '$libdir/vector', 'sparsevec_out'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_recv
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_recv"(internal, oid, int4);
CREATE FUNCTION "public"."sparsevec_recv"(internal, oid, int4)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'sparsevec_recv'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_send
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_send"("public"."sparsevec");
CREATE FUNCTION "public"."sparsevec_send"("public"."sparsevec")
  RETURNS "pg_catalog"."bytea" AS '$libdir/vector', 'sparsevec_send'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_to_halfvec"("public"."sparsevec", int4, bool);
CREATE FUNCTION "public"."sparsevec_to_halfvec"("public"."sparsevec", int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'sparsevec_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_to_vector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_to_vector"("public"."sparsevec", int4, bool);
CREATE FUNCTION "public"."sparsevec_to_vector"("public"."sparsevec", int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'sparsevec_to_vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for sparsevec_typmod_in
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."sparsevec_typmod_in"(_cstring);
CREATE FUNCTION "public"."sparsevec_typmod_in"(_cstring)
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'sparsevec_typmod_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for subvector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."subvector"("public"."vector", int4, int4);
CREATE FUNCTION "public"."subvector"("public"."vector", int4, int4)
  RETURNS "public"."vector" AS '$libdir/vector', 'subvector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for subvector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."subvector"("public"."halfvec", int4, int4);
CREATE FUNCTION "public"."subvector"("public"."halfvec", int4, int4)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'halfvec_subvector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for update_updated_at_column
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."update_updated_at_column"();
CREATE FUNCTION "public"."update_updated_at_column"()
  RETURNS "pg_catalog"."trigger" AS $BODY$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;

-- ----------------------------
-- Function structure for validate_tenant_access
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."validate_tenant_access"("target_tenant_id" text, "operation" text);
CREATE FUNCTION "public"."validate_tenant_access"("target_tenant_id" text, "operation" text='READ'::text)
  RETURNS "pg_catalog"."bool" AS $BODY$
            DECLARE
                current_tenant TEXT;
            BEGIN
                -- 获取当前租户 ID
                current_tenant := current_setting('app.current_tenant_id', true);
                
                -- 如果没有设置租户上下文，拒绝访问
                IF current_tenant IS NULL OR current_tenant = '' THEN
                    RAISE EXCEPTION 'Missing tenant context for operation: %', operation;
                END IF;
                
                -- 检查租户匹配
                IF current_tenant != target_tenant_id THEN
                    RAISE EXCEPTION 'Cross-tenant access denied: % -> %', current_tenant, target_tenant_id;
                END IF;
                
                RETURN TRUE;
            END;
            $BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100;

-- ----------------------------
-- Function structure for vector
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector"("public"."vector", int4, bool);
CREATE FUNCTION "public"."vector"("public"."vector", int4, bool)
  RETURNS "public"."vector" AS '$libdir/vector', 'vector'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_accum
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_accum"(_float8, "public"."vector");
CREATE FUNCTION "public"."vector_accum"(_float8, "public"."vector")
  RETURNS "pg_catalog"."_float8" AS '$libdir/vector', 'vector_accum'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_add
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_add"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_add"("public"."vector", "public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_add'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_avg
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_avg"(_float8);
CREATE FUNCTION "public"."vector_avg"(_float8)
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_avg'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_cmp
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_cmp"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_cmp"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'vector_cmp'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_combine
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_combine"(_float8, _float8);
CREATE FUNCTION "public"."vector_combine"(_float8, _float8)
  RETURNS "pg_catalog"."_float8" AS '$libdir/vector', 'vector_combine'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_concat
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_concat"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_concat"("public"."vector", "public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_concat'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_dims
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_dims"("public"."vector");
CREATE FUNCTION "public"."vector_dims"("public"."vector")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'vector_dims'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_dims
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_dims"("public"."halfvec");
CREATE FUNCTION "public"."vector_dims"("public"."halfvec")
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'halfvec_vector_dims'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_eq
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_eq"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_eq"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_eq'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_ge
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_ge"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_ge"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_ge'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_gt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_gt"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_gt"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_gt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_in
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_in"(cstring, oid, int4);
CREATE FUNCTION "public"."vector_in"(cstring, oid, int4)
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_l2_squared_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_l2_squared_distance"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_l2_squared_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'vector_l2_squared_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_le
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_le"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_le"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_le'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_lt
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_lt"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_lt"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_lt'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_mul
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_mul"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_mul"("public"."vector", "public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_mul'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_ne
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_ne"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_ne"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."bool" AS '$libdir/vector', 'vector_ne'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_negative_inner_product
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_negative_inner_product"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_negative_inner_product"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'vector_negative_inner_product'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_norm
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_norm"("public"."vector");
CREATE FUNCTION "public"."vector_norm"("public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'vector_norm'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_out
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_out"("public"."vector");
CREATE FUNCTION "public"."vector_out"("public"."vector")
  RETURNS "pg_catalog"."cstring" AS '$libdir/vector', 'vector_out'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_recv
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_recv"(internal, oid, int4);
CREATE FUNCTION "public"."vector_recv"(internal, oid, int4)
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_recv'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_send
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_send"("public"."vector");
CREATE FUNCTION "public"."vector_send"("public"."vector")
  RETURNS "pg_catalog"."bytea" AS '$libdir/vector', 'vector_send'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_spherical_distance
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_spherical_distance"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_spherical_distance"("public"."vector", "public"."vector")
  RETURNS "pg_catalog"."float8" AS '$libdir/vector', 'vector_spherical_distance'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_sub
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_sub"("public"."vector", "public"."vector");
CREATE FUNCTION "public"."vector_sub"("public"."vector", "public"."vector")
  RETURNS "public"."vector" AS '$libdir/vector', 'vector_sub'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_to_float4
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_to_float4"("public"."vector", int4, bool);
CREATE FUNCTION "public"."vector_to_float4"("public"."vector", int4, bool)
  RETURNS "pg_catalog"."_float4" AS '$libdir/vector', 'vector_to_float4'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_to_halfvec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_to_halfvec"("public"."vector", int4, bool);
CREATE FUNCTION "public"."vector_to_halfvec"("public"."vector", int4, bool)
  RETURNS "public"."halfvec" AS '$libdir/vector', 'vector_to_halfvec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_to_sparsevec
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_to_sparsevec"("public"."vector", int4, bool);
CREATE FUNCTION "public"."vector_to_sparsevec"("public"."vector", int4, bool)
  RETURNS "public"."sparsevec" AS '$libdir/vector', 'vector_to_sparsevec'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for vector_typmod_in
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."vector_typmod_in"(_cstring);
CREATE FUNCTION "public"."vector_typmod_in"(_cstring)
  RETURNS "pg_catalog"."int4" AS '$libdir/vector', 'vector_typmod_in'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Indexes structure for table agent_collaborations
-- ----------------------------
CREATE INDEX "idx_agent_collab_task" ON "public"."agent_collaborations" USING btree (
  "task_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_collab_tenant_time" ON "public"."agent_collaborations" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "timestamp" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_collaborations
-- ----------------------------
ALTER TABLE "public"."agent_collaborations" ADD CONSTRAINT "agent_collaborations_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_steps
-- ----------------------------
CREATE INDEX "idx_agent_steps_metadata_gin" ON "public"."agent_steps" USING gin (
  "metadata" "pg_catalog"."jsonb_ops"
);
CREATE INDEX "idx_agent_steps_step_number" ON "public"."agent_steps" USING btree (
  "trace_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "step_number" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_steps_tenant_id" ON "public"."agent_steps" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_steps_tool_input_gin" ON "public"."agent_steps" USING gin (
  "tool_input" "pg_catalog"."jsonb_ops"
);
CREATE INDEX "idx_agent_steps_trace_id" ON "public"."agent_steps" USING btree (
  "trace_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_steps_user_id" ON "public"."agent_steps" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_steps
-- ----------------------------
ALTER TABLE "public"."agent_steps" ADD CONSTRAINT "agent_steps_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_task_checkpoints
-- ----------------------------
CREATE INDEX "idx_task_checkpoint_parent" ON "public"."agent_task_checkpoints" USING btree (
  "parent_checkpoint_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_checkpoint_task_created" ON "public"."agent_task_checkpoints" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_checkpoint_task_id" ON "public"."agent_task_checkpoints" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_task_checkpoints
-- ----------------------------
ALTER TABLE "public"."agent_task_checkpoints" ADD CONSTRAINT "agent_task_checkpoints_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_task_events
-- ----------------------------
CREATE INDEX "idx_task_event_task_created" ON "public"."agent_task_events" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_event_task_id" ON "public"."agent_task_events" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_event_tenant_id" ON "public"."agent_task_events" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_task_events
-- ----------------------------
ALTER TABLE "public"."agent_task_events" ADD CONSTRAINT "agent_task_events_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_task_status
-- ----------------------------
CREATE INDEX "idx_task_status_arq_job_id" ON "public"."agent_task_status" USING btree (
  "arq_job_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_request_id" ON "public"."agent_task_status" USING btree (
  "request_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_status" ON "public"."agent_task_status" USING btree (
  "status" "pg_catalog"."enum_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_task_id" ON "public"."agent_task_status" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_tenant_created" ON "public"."agent_task_status" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_tenant_id" ON "public"."agent_task_status" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_thread_id" ON "public"."agent_task_status" USING btree (
  "thread_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_thread_status" ON "public"."agent_task_status" USING btree (
  "thread_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "status" "pg_catalog"."enum_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_user_id" ON "public"."agent_task_status" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_task_status_user_status" ON "public"."agent_task_status" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "status" "pg_catalog"."enum_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table agent_task_status
-- ----------------------------
ALTER TABLE "public"."agent_task_status" ADD CONSTRAINT "agent_task_status_task_id_key" UNIQUE ("task_id");

-- ----------------------------
-- Primary Key structure for table agent_task_status
-- ----------------------------
ALTER TABLE "public"."agent_task_status" ADD CONSTRAINT "agent_task_status_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table agent_traces
-- ----------------------------
CREATE INDEX "idx_agent_traces_created_at" ON "public"."agent_traces" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" DESC NULLS FIRST
);
CREATE INDEX "idx_agent_traces_session_id" ON "public"."agent_traces" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_traces_tenant_id" ON "public"."agent_traces" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_agent_traces_user_id" ON "public"."agent_traces" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_agent_traces_model_name" ON "public"."agent_traces" USING btree (
  "model_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_traces
-- ----------------------------
ALTER TABLE "public"."agent_traces" ADD CONSTRAINT "agent_traces_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table alembic_version
-- ----------------------------
ALTER TABLE "public"."alembic_version" ADD CONSTRAINT "alembic_version_pkc" PRIMARY KEY ("version_num");

-- ----------------------------
-- Indexes structure for table audit_results
-- ----------------------------
CREATE INDEX "idx_audit_results_agent" ON "public"."audit_results" USING btree (
  "agent_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_audit_results_tenant_task" ON "public"."audit_results" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "task_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table audit_results
-- ----------------------------
ALTER TABLE "public"."audit_results" ADD CONSTRAINT "audit_results_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table audit_tasks
-- ----------------------------
CREATE INDEX "idx_audit_tasks_status" ON "public"."audit_tasks" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_audit_tasks_tenant" ON "public"."audit_tasks" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_audit_tasks_user" ON "public"."audit_tasks" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table audit_tasks
-- ----------------------------
ALTER TABLE "public"."audit_tasks" ADD CONSTRAINT "audit_tasks_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table chat_groups
-- ----------------------------
CREATE INDEX "idx_chat_groups_tenant_id" ON "public"."chat_groups" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table chat_groups
-- ----------------------------
ALTER TABLE "public"."chat_groups" ADD CONSTRAINT "chat_groups_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table chat_messages
-- ----------------------------
CREATE INDEX "chat_messages_embedding_hnsw" ON "public"."chat_messages" (
  "embedding" "public"."vector_cosine_ops" ASC NULLS LAST
);
CREATE INDEX "idx_messages_tenant" ON "public"."chat_messages" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_messages_tenant_id" ON "public"."chat_messages" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table chat_messages
-- ----------------------------
ALTER TABLE "public"."chat_messages" ADD CONSTRAINT "chat_messages_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table chat_sessions
-- ----------------------------
CREATE INDEX "idx_sessions_tenant" ON "public"."chat_sessions" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_sessions_tenant_id" ON "public"."chat_sessions" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table chat_sessions
-- ----------------------------
ALTER TABLE "public"."chat_sessions" ADD CONSTRAINT "chat_sessions_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table contract_clauses
-- ----------------------------
CREATE INDEX "ix_contract_clauses_clause_type" ON "public"."contract_clauses" USING btree (
  "clause_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_contract_clauses_report_id" ON "public"."contract_clauses" USING btree (
  "report_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table contract_clauses
-- ----------------------------
ALTER TABLE "public"."contract_clauses" ADD CONSTRAINT "contract_clauses_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table contract_comparison_history
-- ----------------------------
CREATE INDEX "ix_contract_comparison_history_tenant_id" ON "public"."contract_comparison_history" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_contract_comparison_history_user_id" ON "public"."contract_comparison_history" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table contract_comparison_history
-- ----------------------------
ALTER TABLE "public"."contract_comparison_history" ADD CONSTRAINT "contract_comparison_history_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table contract_review_reports
-- ----------------------------
CREATE INDEX "ix_contract_review_reports_created_at" ON "public"."contract_review_reports" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_contract_review_reports_review_status" ON "public"."contract_review_reports" USING btree (
  "review_status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_contract_review_reports_tenant_id" ON "public"."contract_review_reports" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_contract_review_reports_user_id" ON "public"."contract_review_reports" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table contract_review_reports
-- ----------------------------
ALTER TABLE "public"."contract_review_reports" ADD CONSTRAINT "contract_review_reports_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table contract_templates
-- ----------------------------
CREATE INDEX "ix_contract_templates_tenant_id" ON "public"."contract_templates" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table contract_templates
-- ----------------------------
ALTER TABLE "public"."contract_templates" ADD CONSTRAINT "contract_templates_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table custom_tools
-- ----------------------------
CREATE INDEX "ix_custom_tools_agent_id" ON "public"."custom_tools" USING btree (
  "agent_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_custom_tools_created_by" ON "public"."custom_tools" USING btree (
  "created_by" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_custom_tools_enabled" ON "public"."custom_tools" USING btree (
  "enabled" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "ix_custom_tools_kind" ON "public"."custom_tools" USING btree (
  "kind" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_custom_tools_name" ON "public"."custom_tools" USING btree (
  "name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_custom_tools_status" ON "public"."custom_tools" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_custom_tools_tenant_id" ON "public"."custom_tools" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_custom_tools_tenant_name_version" ON "public"."custom_tools" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "version" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table custom_tools
-- ----------------------------
ALTER TABLE "public"."custom_tools" ADD CONSTRAINT "uq_custom_tools_tenant_name_version" UNIQUE ("tenant_id", "name", "version");

-- ----------------------------
-- Primary Key structure for table custom_tools
-- ----------------------------
ALTER TABLE "public"."custom_tools" ADD CONSTRAINT "custom_tools_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table document_chunks
-- ----------------------------
CREATE INDEX "document_chunks_embedding_hnsw" ON "public"."document_chunks" (
  "embedding" "public"."vector_cosine_ops" ASC NULLS LAST
);
CREATE INDEX "idx_chunks_domain" ON "public"."document_chunks" USING btree (
  "domain" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_chunks_node_hash" ON "public"."document_chunks" USING btree (
  "node_hash" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_chunks_node_type" ON "public"."document_chunks" USING btree (
  "node_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_chunks_tsvector" ON "public"."document_chunks" USING gin (
  "content_tsvector" "pg_catalog"."tsvector_ops"
);
CREATE INDEX "idx_document_chunks_fts" ON "public"."document_chunks" USING gin (
  "fts_vector" "pg_catalog"."tsvector_ops"
);
CREATE INDEX "idx_document_chunks_tenant_id" ON "public"."document_chunks" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Triggers structure for table document_chunks
-- ----------------------------
CREATE TRIGGER "audit_tenant_access_document_chunks" BEFORE INSERT OR UPDATE OR DELETE ON "public"."document_chunks"
FOR EACH ROW
EXECUTE PROCEDURE "public"."log_tenant_access"();

-- ----------------------------
-- Primary Key structure for table document_chunks
-- ----------------------------
ALTER TABLE "public"."document_chunks" ADD CONSTRAINT "document_chunks_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table documents
-- ----------------------------
CREATE INDEX "idx_docs_tenant_id" ON "public"."documents" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_documents_embedding_hnsw" ON "public"."documents" (
  "embedding" "public"."halfvec_cosine_ops" ASC NULLS LAST
);
CREATE INDEX "idx_documents_tenant" ON "public"."documents" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_documents_visibility" ON "public"."documents" USING btree (
  "visibility" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_documents_hash" ON "public"."documents" USING btree (
  "hash" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_documents_processing_state" ON "public"."documents" USING btree (
  "processing_state" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Triggers structure for table documents
-- ----------------------------
CREATE TRIGGER "audit_tenant_access_documents" BEFORE INSERT OR UPDATE OR DELETE ON "public"."documents"
FOR EACH ROW
EXECUTE PROCEDURE "public"."log_tenant_access"();

-- ----------------------------
-- Primary Key structure for table documents
-- ----------------------------
ALTER TABLE "public"."documents" ADD CONSTRAINT "documents_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table enrichment_jobs
-- ----------------------------
CREATE INDEX "idx_enrichment_jobs_document_id" ON "public"."enrichment_jobs" USING btree (
  "document_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_enrichment_jobs_job_type" ON "public"."enrichment_jobs" USING btree (
  "job_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_enrichment_jobs_status" ON "public"."enrichment_jobs" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table enrichment_jobs
-- ----------------------------
ALTER TABLE "public"."enrichment_jobs" ADD CONSTRAINT "enrichment_jobs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table enterprise_policy_matches
-- ----------------------------
CREATE INDEX "idx_matches_acknowledged" ON "public"."enterprise_policy_matches" USING btree (
  "acknowledged" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "idx_matches_enterprise" ON "public"."enterprise_policy_matches" USING btree (
  "enterprise_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_matches_notification_status" ON "public"."enterprise_policy_matches" USING btree (
  "notification_status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_matches_policy" ON "public"."enterprise_policy_matches" USING btree (
  "policy_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table enterprise_policy_matches
-- ----------------------------
ALTER TABLE "public"."enterprise_policy_matches" ADD CONSTRAINT "enterprise_policy_matches_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table episodic_memories
-- ----------------------------
CREATE INDEX "idx_episodic_memories_created_at" ON "public"."episodic_memories" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_episodic_memories_session_id" ON "public"."episodic_memories" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_episodic_memories_user_id" ON "public"."episodic_memories" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table episodic_memories
-- ----------------------------
ALTER TABLE "public"."episodic_memories" ADD CONSTRAINT "episodic_memories_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table failure_cases
-- ----------------------------
CREATE INDEX "ix_failure_cases_feedback_id" ON "public"."failure_cases" USING btree (
  "feedback_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table failure_cases
-- ----------------------------
ALTER TABLE "public"."failure_cases" ADD CONSTRAINT "failure_cases_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table financial_anomaly_records
-- ----------------------------
CREATE INDEX "ix_financial_anomaly_records_anomaly_type" ON "public"."financial_anomaly_records" USING btree (
  "anomaly_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_anomaly_records_created_at" ON "public"."financial_anomaly_records" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_anomaly_records_report_id" ON "public"."financial_anomaly_records" USING btree (
  "report_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_anomaly_records_status" ON "public"."financial_anomaly_records" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_anomaly_records_tenant_id" ON "public"."financial_anomaly_records" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_anomaly_records_user_id" ON "public"."financial_anomaly_records" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table financial_anomaly_records
-- ----------------------------
ALTER TABLE "public"."financial_anomaly_records" ADD CONSTRAINT "financial_anomaly_records_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table financial_data_history
-- ----------------------------
CREATE INDEX "ix_financial_data_history_financial_data_id" ON "public"."financial_data_history" USING btree (
  "financial_data_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table financial_data_history
-- ----------------------------
ALTER TABLE "public"."financial_data_history" ADD CONSTRAINT "financial_data_history_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table financial_health_reports
-- ----------------------------
CREATE INDEX "ix_financial_health_reports_created_at" ON "public"."financial_health_reports" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_health_reports_status" ON "public"."financial_health_reports" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_health_reports_tenant_id" ON "public"."financial_health_reports" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_health_reports_user_id" ON "public"."financial_health_reports" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table financial_health_reports
-- ----------------------------
ALTER TABLE "public"."financial_health_reports" ADD CONSTRAINT "financial_health_reports_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table financial_thresholds
-- ----------------------------
CREATE INDEX "ix_financial_thresholds_metric_name" ON "public"."financial_thresholds" USING btree (
  "metric_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_thresholds_tenant_id" ON "public"."financial_thresholds" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table financial_thresholds
-- ----------------------------
ALTER TABLE "public"."financial_thresholds" ADD CONSTRAINT "financial_thresholds_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table financial_trend_data
-- ----------------------------
CREATE INDEX "ix_financial_trend_data_created_at" ON "public"."financial_trend_data" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_trend_data_metric_name" ON "public"."financial_trend_data" USING btree (
  "metric_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_trend_data_record_date" ON "public"."financial_trend_data" USING btree (
  "record_date" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_trend_data_tenant_id" ON "public"."financial_trend_data" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_financial_trend_data_user_id" ON "public"."financial_trend_data" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table financial_trend_data
-- ----------------------------
ALTER TABLE "public"."financial_trend_data" ADD CONSTRAINT "financial_trend_data_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table group_invitations
-- ----------------------------
CREATE INDEX "idx_group_invitations_tenant_id" ON "public"."group_invitations" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table group_invitations
-- ----------------------------
ALTER TABLE "public"."group_invitations" ADD CONSTRAINT "group_invitations_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table group_members
-- ----------------------------
CREATE INDEX "idx_group_members_group_id" ON "public"."group_members" USING btree (
  "group_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_group_members_tenant_id" ON "public"."group_members" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table group_members
-- ----------------------------
ALTER TABLE "public"."group_members" ADD CONSTRAINT "group_members_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table group_messages
-- ----------------------------
CREATE INDEX "idx_group_messages_group_id" ON "public"."group_messages" USING btree (
  "group_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_group_messages_tenant_id" ON "public"."group_messages" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table group_messages
-- ----------------------------
ALTER TABLE "public"."group_messages" ADD CONSTRAINT "group_messages_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table improvement_records
-- ----------------------------
CREATE INDEX "ix_improvement_records_failure_case_id" ON "public"."improvement_records" USING btree (
  "failure_case_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table improvement_records
-- ----------------------------
ALTER TABLE "public"."improvement_records" ADD CONSTRAINT "improvement_records_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table invite_code_usages
-- ----------------------------
CREATE INDEX "idx_invite_code_usages_invite_code_id" ON "public"."invite_code_usages" USING btree (
  "invite_code_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_invite_code_usages_used_at" ON "public"."invite_code_usages" USING btree (
  "used_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_invite_code_usages_user_id" ON "public"."invite_code_usages" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table invite_code_usages
-- ----------------------------
ALTER TABLE "public"."invite_code_usages" ADD CONSTRAINT "invite_code_usages_invite_code_id_user_id_key" UNIQUE ("invite_code_id", "user_id");

-- ----------------------------
-- Primary Key structure for table invite_code_usages
-- ----------------------------
ALTER TABLE "public"."invite_code_usages" ADD CONSTRAINT "invite_code_usages_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table invite_codes
-- ----------------------------
CREATE INDEX "idx_invite_codes_active" ON "public"."invite_codes" USING btree (
  "is_active" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "idx_invite_codes_code" ON "public"."invite_codes" USING btree (
  "code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_invite_codes_created_by" ON "public"."invite_codes" USING btree (
  "created_by" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_invite_codes_expires_at" ON "public"."invite_codes" USING btree (
  "expires_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_invite_codes_tenant_id" ON "public"."invite_codes" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Triggers structure for table invite_codes
-- ----------------------------
CREATE TRIGGER "update_invite_codes_updated_at" BEFORE UPDATE ON "public"."invite_codes"
FOR EACH ROW
EXECUTE PROCEDURE "public"."update_updated_at_column"();

-- ----------------------------
-- Uniques structure for table invite_codes
-- ----------------------------
ALTER TABLE "public"."invite_codes" ADD CONSTRAINT "invite_codes_code_key" UNIQUE ("code");

-- ----------------------------
-- Primary Key structure for table invite_codes
-- ----------------------------
ALTER TABLE "public"."invite_codes" ADD CONSTRAINT "invite_codes_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table knowledge_bases
-- ----------------------------
CREATE INDEX "idx_kb_tenant" ON "public"."knowledge_bases" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_kb_tenant_id" ON "public"."knowledge_bases" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_knowledge_bases_tenant_id" ON "public"."knowledge_bases" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_knowledge_bases_visibility" ON "public"."knowledge_bases" USING btree (
  "visibility" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Triggers structure for table knowledge_bases
-- ----------------------------
CREATE TRIGGER "audit_tenant_access_knowledge_bases" BEFORE INSERT OR UPDATE OR DELETE ON "public"."knowledge_bases"
FOR EACH ROW
EXECUTE PROCEDURE "public"."log_tenant_access"();

-- ----------------------------
-- Primary Key structure for table knowledge_bases
-- ----------------------------
ALTER TABLE "public"."knowledge_bases" ADD CONSTRAINT "knowledge_bases_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table langgraph_checkpoints
-- ----------------------------
CREATE INDEX "idx_langgraph_checkpoints_parent" ON "public"."langgraph_checkpoints" USING btree (
  "parent_checkpoint_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_langgraph_checkpoints_thread_id" ON "public"."langgraph_checkpoints" USING btree (
  "thread_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_langgraph_checkpoints_updated_at" ON "public"."langgraph_checkpoints" USING btree (
  "updated_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_lg_checkpoint_parent" ON "public"."langgraph_checkpoints" USING btree (
  "parent_checkpoint_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_lg_checkpoint_thread" ON "public"."langgraph_checkpoints" USING btree (
  "thread_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_lg_checkpoint_updated" ON "public"."langgraph_checkpoints" USING btree (
  "updated_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table langgraph_checkpoints
-- ----------------------------
ALTER TABLE "public"."langgraph_checkpoints" ADD CONSTRAINT "langgraph_checkpoints_pkey" PRIMARY KEY ("thread_id", "checkpoint_id");

-- ----------------------------
-- Indexes structure for table multi_agent_intent_analyses
-- ----------------------------
CREATE INDEX "idx_ma_intent_session" ON "public"."multi_agent_intent_analyses" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_intent_analyses_session_id" ON "public"."multi_agent_intent_analyses" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_intent_analyses_tenant_id" ON "public"."multi_agent_intent_analyses" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table multi_agent_intent_analyses
-- ----------------------------
ALTER TABLE "public"."multi_agent_intent_analyses" ADD CONSTRAINT "multi_agent_intent_analyses_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table multi_agent_reflection_records
-- ----------------------------
CREATE INDEX "idx_ma_reflection_session" ON "public"."multi_agent_reflection_records" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_reflection_records_session_id" ON "public"."multi_agent_reflection_records" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_reflection_records_tenant_id" ON "public"."multi_agent_reflection_records" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table multi_agent_reflection_records
-- ----------------------------
ALTER TABLE "public"."multi_agent_reflection_records" ADD CONSTRAINT "multi_agent_reflection_records_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table multi_agent_report_access_logs
-- ----------------------------
CREATE INDEX "idx_ma_report_access_report" ON "public"."multi_agent_report_access_logs" USING btree (
  "report_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_ma_report_access_tenant" ON "public"."multi_agent_report_access_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_ma_report_access_user" ON "public"."multi_agent_report_access_logs" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_report_access_logs_report_id" ON "public"."multi_agent_report_access_logs" USING btree (
  "report_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_report_access_logs_tenant_id" ON "public"."multi_agent_report_access_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table multi_agent_report_access_logs
-- ----------------------------
ALTER TABLE "public"."multi_agent_report_access_logs" ADD CONSTRAINT "multi_agent_report_access_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table multi_agent_report_versions
-- ----------------------------
CREATE INDEX "idx_ma_report_version_report" ON "public"."multi_agent_report_versions" USING btree (
  "report_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "version" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_report_versions_report_id" ON "public"."multi_agent_report_versions" USING btree (
  "report_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_report_versions_tenant_id" ON "public"."multi_agent_report_versions" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table multi_agent_report_versions
-- ----------------------------
ALTER TABLE "public"."multi_agent_report_versions" ADD CONSTRAINT "multi_agent_report_versions_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table multi_agent_reports
-- ----------------------------
CREATE INDEX "idx_ma_report_session_latest" ON "public"."multi_agent_reports" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "is_latest" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "idx_ma_report_tenant_created" ON "public"."multi_agent_reports" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_ma_report_type" ON "public"."multi_agent_reports" USING btree (
  "report_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_reports_session_id" ON "public"."multi_agent_reports" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_reports_tenant_id" ON "public"."multi_agent_reports" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table multi_agent_reports
-- ----------------------------
ALTER TABLE "public"."multi_agent_reports" ADD CONSTRAINT "multi_agent_reports_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table multi_agent_sessions
-- ----------------------------
CREATE INDEX "idx_ma_session_tenant_created" ON "public"."multi_agent_sessions" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_ma_session_user" ON "public"."multi_agent_sessions" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_multi_agent_sessions_session_id" ON "public"."multi_agent_sessions" USING btree (
  "session_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_sessions_tenant_id" ON "public"."multi_agent_sessions" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table multi_agent_sessions
-- ----------------------------
ALTER TABLE "public"."multi_agent_sessions" ADD CONSTRAINT "multi_agent_sessions_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table multi_agent_specialist_results
-- ----------------------------
CREATE INDEX "idx_ma_specialist_session" ON "public"."multi_agent_specialist_results" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "execution_order" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_specialist_results_session_id" ON "public"."multi_agent_specialist_results" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_multi_agent_specialist_results_tenant_id" ON "public"."multi_agent_specialist_results" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table multi_agent_specialist_results
-- ----------------------------
ALTER TABLE "public"."multi_agent_specialist_results" ADD CONSTRAINT "multi_agent_specialist_results_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table policies
-- ----------------------------
CREATE INDEX "idx_policies_embedding_hnsw" ON "public"."policies" (
  "embedding" "public"."halfvec_cosine_ops" ASC NULLS LAST
);
CREATE INDEX "idx_policies_policy_id" ON "public"."policies" USING btree (
  "policy_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_policies_priority" ON "public"."policies" USING btree (
  "priority" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_policies_published_date" ON "public"."policies" USING btree (
  "published_date" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_policies_status" ON "public"."policies" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_policies_tenant_id" ON "public"."policies" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table policies
-- ----------------------------
ALTER TABLE "public"."policies" ADD CONSTRAINT "policies_policy_id_key" UNIQUE ("policy_id");

-- ----------------------------
-- Primary Key structure for table policies
-- ----------------------------
ALTER TABLE "public"."policies" ADD CONSTRAINT "policies_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table policy_relations
-- ----------------------------
CREATE INDEX "idx_policy_relations_source" ON "public"."policy_relations" USING btree (
  "source_policy_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_policy_relations_target" ON "public"."policy_relations" USING btree (
  "target_policy_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_policy_relations_type" ON "public"."policy_relations" USING btree (
  "relation_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table policy_relations
-- ----------------------------
ALTER TABLE "public"."policy_relations" ADD CONSTRAINT "policy_relations_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table prompt_ab_tests
-- ----------------------------
CREATE INDEX "idx_prompt_ab_tests_status" ON "public"."prompt_ab_tests" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table prompt_ab_tests
-- ----------------------------
ALTER TABLE "public"."prompt_ab_tests" ADD CONSTRAINT "prompt_ab_tests_test_name_key" UNIQUE ("test_name");

-- ----------------------------
-- Primary Key structure for table prompt_ab_tests
-- ----------------------------
ALTER TABLE "public"."prompt_ab_tests" ADD CONSTRAINT "prompt_ab_tests_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table prompt_executions
-- ----------------------------
CREATE INDEX "idx_prompt_executions_created_at" ON "public"."prompt_executions" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" DESC NULLS FIRST
);
CREATE INDEX "idx_prompt_executions_template_id" ON "public"."prompt_executions" USING btree (
  "template_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table prompt_executions
-- ----------------------------
ALTER TABLE "public"."prompt_executions" ADD CONSTRAINT "prompt_executions_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table prompt_templates
-- ----------------------------
ALTER TABLE "public"."prompt_templates" ADD CONSTRAINT "prompt_templates_name_key" UNIQUE ("name");

-- ----------------------------
-- Primary Key structure for table prompt_templates
-- ----------------------------
ALTER TABLE "public"."prompt_templates" ADD CONSTRAINT "prompt_templates_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table review_request_actions
-- ----------------------------
CREATE INDEX "ix_review_request_actions_request_created" ON "public"."review_request_actions" USING btree (
  "review_request_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_request_actions_review_request_id" ON "public"."review_request_actions" USING btree (
  "review_request_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_request_actions_user_created" ON "public"."review_request_actions" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_request_actions_user_id" ON "public"."review_request_actions" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table review_request_actions
-- ----------------------------
ALTER TABLE "public"."review_request_actions" ADD CONSTRAINT "review_request_actions_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table review_request_comments
-- ----------------------------
CREATE INDEX "ix_review_request_comments_request_created" ON "public"."review_request_comments" USING btree (
  "review_request_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_request_comments_review_request_id" ON "public"."review_request_comments" USING btree (
  "review_request_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_request_comments_user_id" ON "public"."review_request_comments" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table review_request_comments
-- ----------------------------
ALTER TABLE "public"."review_request_comments" ADD CONSTRAINT "review_request_comments_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table review_requests
-- ----------------------------
CREATE INDEX "ix_review_requests_assigned_status" ON "public"."review_requests" USING btree (
  "assigned_to" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_requests_assigned_to" ON "public"."review_requests" USING btree (
  "assigned_to" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_requests_created_at" ON "public"."review_requests" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_requests_status" ON "public"."review_requests" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_requests_task_id" ON "public"."review_requests" USING btree (
  "task_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_requests_tenant_id" ON "public"."review_requests" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_requests_tenant_priority" ON "public"."review_requests" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "priority" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_requests_tenant_status" ON "public"."review_requests" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_review_requests_user_id" ON "public"."review_requests" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table review_requests
-- ----------------------------
ALTER TABLE "public"."review_requests" ADD CONSTRAINT "review_requests_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table scheduled_tasks
-- ----------------------------
CREATE INDEX "ix_scheduled_tasks_next_run_time" ON "public"."scheduled_tasks" USING btree (
  "next_run_time" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scheduled_tasks_status" ON "public"."scheduled_tasks" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_scheduled_tasks_task_id" ON "public"."scheduled_tasks" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scheduled_tasks_task_type" ON "public"."scheduled_tasks" USING btree (
  "task_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scheduled_tasks_tenant_id" ON "public"."scheduled_tasks" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_scheduled_tasks_user_id" ON "public"."scheduled_tasks" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table scheduled_tasks
-- ----------------------------
ALTER TABLE "public"."scheduled_tasks" ADD CONSTRAINT "scheduled_tasks_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table search_logs
-- ----------------------------
ALTER TABLE "public"."search_logs" ADD CONSTRAINT "search_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table semantic_memories
-- ----------------------------
CREATE INDEX "idx_semantic_memories_importance" ON "public"."semantic_memories" USING btree (
  "importance" "pg_catalog"."float8_ops" DESC NULLS FIRST
);
CREATE INDEX "idx_semantic_memories_last_accessed" ON "public"."semantic_memories" USING btree (
  "last_accessed" "pg_catalog"."timestamptz_ops" DESC NULLS FIRST
);
CREATE INDEX "idx_semantic_memories_user_id" ON "public"."semantic_memories" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "semantic_memories_embedding_hnsw" ON "public"."semantic_memories" (
  "embedding" "public"."vector_cosine_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table semantic_memories
-- ----------------------------
ALTER TABLE "public"."semantic_memories" ADD CONSTRAINT "semantic_memories_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table system_logs
-- ----------------------------
CREATE INDEX "idx_system_logs_action" ON "public"."system_logs" USING btree (
  "action" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_action_time" ON "public"."system_logs" USING btree (
  "action" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_category" ON "public"."system_logs" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_category_level" ON "public"."system_logs" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "level" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_created_at" ON "public"."system_logs" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_ip_address" ON "public"."system_logs" USING btree (
  "ip_address" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_level" ON "public"."system_logs" USING btree (
  "level" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_request_id" ON "public"."system_logs" USING btree (
  "request_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_session_id" ON "public"."system_logs" USING btree (
  "session_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_session_time" ON "public"."system_logs" USING btree (
  "session_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_user_id" ON "public"."system_logs" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_logs_user_time" ON "public"."system_logs" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_system_logs_tenant_id" ON "public"."system_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table system_logs
-- ----------------------------
ALTER TABLE "public"."system_logs" ADD CONSTRAINT "system_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table system_settings
-- ----------------------------
ALTER TABLE "public"."system_settings" ADD CONSTRAINT "system_settings_pkey" PRIMARY KEY ("key");

-- ----------------------------
-- Indexes structure for table task_execution_logs
-- ----------------------------
CREATE INDEX "ix_task_execution_logs_scheduled_task_id" ON "public"."task_execution_logs" USING btree (
  "scheduled_task_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_execution_logs_status" ON "public"."task_execution_logs" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_execution_logs_task_id" ON "public"."task_execution_logs" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_execution_logs_tenant_id" ON "public"."task_execution_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_execution_logs_user_id" ON "public"."task_execution_logs" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table task_execution_logs
-- ----------------------------
ALTER TABLE "public"."task_execution_logs" ADD CONSTRAINT "task_execution_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table task_notifications
-- ----------------------------
CREATE INDEX "ix_task_notifications_execution_log_id" ON "public"."task_notifications" USING btree (
  "execution_log_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_notifications_status" ON "public"."task_notifications" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_notifications_task_id" ON "public"."task_notifications" USING btree (
  "task_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_notifications_tenant_id" ON "public"."task_notifications" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_task_notifications_user_id" ON "public"."task_notifications" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table task_notifications
-- ----------------------------
ALTER TABLE "public"."task_notifications" ADD CONSTRAINT "task_notifications_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tax_report_documents
-- ----------------------------
CREATE INDEX "ix_tax_report_documents_status" ON "public"."tax_report_documents" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tax_report_documents_tax_report_id" ON "public"."tax_report_documents" USING btree (
  "tax_report_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table tax_report_documents
-- ----------------------------
ALTER TABLE "public"."tax_report_documents" ADD CONSTRAINT "tax_report_documents_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tax_reports
-- ----------------------------
CREATE INDEX "ix_tax_reports_audit_task_id" ON "public"."tax_reports" USING btree (
  "audit_task_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tax_reports_needs_human_review" ON "public"."tax_reports" USING btree (
  "needs_human_review" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tax_reports_status" ON "public"."tax_reports" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tax_reports_tenant_id" ON "public"."tax_reports" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tax_reports_user_id" ON "public"."tax_reports" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table tax_reports
-- ----------------------------
ALTER TABLE "public"."tax_reports" ADD CONSTRAINT "tax_reports_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tenant_audit_logs
-- ----------------------------
CREATE INDEX "idx_audit_log_result" ON "public"."tenant_audit_logs" USING btree (
  "access_result" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_audit_log_tenant_time" ON "public"."tenant_audit_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_audit_log_user" ON "public"."tenant_audit_logs" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table tenant_audit_logs
-- ----------------------------
ALTER TABLE "public"."tenant_audit_logs" ADD CONSTRAINT "tenant_audit_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tenant_settings
-- ----------------------------
CREATE INDEX "idx_tenant_settings_industry" ON "public"."tenant_settings" USING btree (
  "industry" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_tenant_settings_region" ON "public"."tenant_settings" USING btree (
  "region" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_tenant_settings_tenant_id" ON "public"."tenant_settings" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tenant_settings
-- ----------------------------
ALTER TABLE "public"."tenant_settings" ADD CONSTRAINT "tenant_settings_tenant_id_key" UNIQUE ("tenant_id");

-- ----------------------------
-- Primary Key structure for table tenant_settings
-- ----------------------------
ALTER TABLE "public"."tenant_settings" ADD CONSTRAINT "tenant_settings_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tool_call_traces
-- ----------------------------
CREATE INDEX "idx_tool_call_traces_input_params_gin" ON "public"."tool_call_traces" USING gin (
  "input_params" "pg_catalog"."jsonb_ops"
);
CREATE INDEX "idx_tool_call_traces_metadata_gin" ON "public"."tool_call_traces" USING gin (
  "metadata" "pg_catalog"."jsonb_ops"
);
CREATE INDEX "idx_tool_calls_created_at" ON "public"."tool_call_traces" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" DESC NULLS FIRST
);
CREATE INDEX "idx_tool_calls_tool_name" ON "public"."tool_call_traces" USING btree (
  "tool_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_tool_calls_trace_id" ON "public"."tool_call_traces" USING btree (
  "trace_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tool_call_traces_session_id" ON "public"."tool_call_traces" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tool_call_traces_tenant_id" ON "public"."tool_call_traces" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_tool_call_traces_user_id" ON "public"."tool_call_traces" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table tool_call_traces
-- ----------------------------
ALTER TABLE "public"."tool_call_traces" ADD CONSTRAINT "tool_call_traces_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table update_history
-- ----------------------------
CREATE INDEX "idx_update_history_source" ON "public"."update_history" USING btree (
  "source_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_update_history_started" ON "public"."update_history" USING btree (
  "started_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_update_history_status" ON "public"."update_history" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table update_history
-- ----------------------------
ALTER TABLE "public"."update_history" ADD CONSTRAINT "update_history_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table user_action_logs
-- ----------------------------
CREATE INDEX "idx_action_logs_tenant_risk_time" ON "public"."user_action_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "risk_level" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_action_logs_tenant_time" ON "public"."user_action_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_user_action_logs_action_type" ON "public"."user_action_logs" USING btree (
  "action_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_user_action_logs_created_at" ON "public"."user_action_logs" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_user_action_logs_resource" ON "public"."user_action_logs" USING btree (
  "resource_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "resource_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_user_action_logs_type_time" ON "public"."user_action_logs" USING btree (
  "action_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "idx_user_action_logs_user_id" ON "public"."user_action_logs" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "idx_user_action_logs_user_time" ON "public"."user_action_logs" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_action_logs_risk_level" ON "public"."user_action_logs" USING btree (
  "risk_level" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_action_logs_tenant_id" ON "public"."user_action_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table user_action_logs
-- ----------------------------
ALTER TABLE "public"."user_action_logs" ADD CONSTRAINT "user_action_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table user_feedback
-- ----------------------------
CREATE INDEX "ix_user_feedback_session_id" ON "public"."user_feedback" USING btree (
  "session_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_feedback_tenant_id" ON "public"."user_feedback" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table user_feedback
-- ----------------------------
ALTER TABLE "public"."user_feedback" ADD CONSTRAINT "user_feedback_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table user_financial_data
-- ----------------------------
CREATE INDEX "idx_user_financial_data_fiscal_year_period" ON "public"."user_financial_data" USING btree (
  "fiscal_year" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "period_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_user_financial_data_period_type" ON "public"."user_financial_data" USING btree (
  "period_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_user_financial_data_user_id" ON "public"."user_financial_data" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_financial_data_fiscal_year" ON "public"."user_financial_data" USING btree (
  "fiscal_year" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_financial_data_lookup" ON "public"."user_financial_data" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "fiscal_year" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "period_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_financial_data_tenant_id" ON "public"."user_financial_data" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_financial_data_tenant_year" ON "public"."user_financial_data" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "fiscal_year" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_financial_data_user_id" ON "public"."user_financial_data" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_financial_data_user_year" ON "public"."user_financial_data" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "fiscal_year" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table user_financial_data
-- ----------------------------
ALTER TABLE "public"."user_financial_data" ADD CONSTRAINT "user_financial_data_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table user_multimodal_configs
-- ----------------------------
CREATE INDEX "ix_user_multimodal_configs_tenant_id" ON "public"."user_multimodal_configs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table user_multimodal_configs
-- ----------------------------
ALTER TABLE "public"."user_multimodal_configs" ADD CONSTRAINT "uq_tenant_multimodal_config" UNIQUE ("tenant_id");

-- ----------------------------
-- Primary Key structure for table user_multimodal_configs
-- ----------------------------
ALTER TABLE "public"."user_multimodal_configs" ADD CONSTRAINT "user_multimodal_configs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table user_multimodal_usage_logs
-- ----------------------------
CREATE INDEX "ix_user_multimodal_usage_logs_created_at" ON "public"."user_multimodal_usage_logs" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_multimodal_usage_logs_document_id" ON "public"."user_multimodal_usage_logs" USING btree (
  "document_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_user_multimodal_usage_logs_tenant_id" ON "public"."user_multimodal_usage_logs" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table user_multimodal_usage_logs
-- ----------------------------
ALTER TABLE "public"."user_multimodal_usage_logs" ADD CONSTRAINT "user_multimodal_usage_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table users
-- ----------------------------
CREATE INDEX "idx_users_nickname" ON "public"."users" USING btree (
  "nickname" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "idx_users_phone" ON "public"."users" USING btree (
  "phone" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
) WHERE phone IS NOT NULL;
CREATE INDEX "idx_users_tenant" ON "public"."users" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_users_tenant_id" ON "public"."users" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_users_email" ON "public"."users" USING btree (
  "email" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Triggers structure for table users
-- ----------------------------
CREATE TRIGGER "audit_tenant_access_users" BEFORE INSERT OR UPDATE OR DELETE ON "public"."users"
FOR EACH ROW
EXECUTE PROCEDURE "public"."log_tenant_access"();

-- ----------------------------
-- Primary Key structure for table users
-- ----------------------------
ALTER TABLE "public"."users" ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table workflow_node_executions
-- ----------------------------
CREATE INDEX "ix_workflow_node_executions_agent_trace_id" ON "public"."workflow_node_executions" USING btree (
  "agent_trace_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_node_executions_node_name" ON "public"."workflow_node_executions" USING btree (
  "node_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_node_executions_trace_order" ON "public"."workflow_node_executions" USING btree (
  "workflow_trace_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "execution_order" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_node_executions_workflow_trace_id" ON "public"."workflow_node_executions" USING btree (
  "workflow_trace_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table workflow_node_executions
-- ----------------------------
ALTER TABLE "public"."workflow_node_executions" ADD CONSTRAINT "workflow_node_executions_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table workflow_traces
-- ----------------------------
CREATE INDEX "ix_workflow_traces_created_at" ON "public"."workflow_traces" USING btree (
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_traces_human_review_id" ON "public"."workflow_traces" USING btree (
  "human_review_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_traces_session_id" ON "public"."workflow_traces" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_traces_status" ON "public"."workflow_traces" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_traces_tenant_id" ON "public"."workflow_traces" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_traces_tenant_status" ON "public"."workflow_traces" USING btree (
  "tenant_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_traces_user_created" ON "public"."workflow_traces" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_traces_user_id" ON "public"."workflow_traces" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_workflow_traces_workflow_type" ON "public"."workflow_traces" USING btree (
  "workflow_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table workflow_traces
-- ----------------------------
ALTER TABLE "public"."workflow_traces" ADD CONSTRAINT "workflow_traces_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table agent_collaborations
-- ----------------------------
ALTER TABLE "public"."agent_collaborations" ADD CONSTRAINT "agent_collaborations_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "public"."audit_tasks" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table agent_steps
-- ----------------------------
ALTER TABLE "public"."agent_steps" ADD CONSTRAINT "agent_steps_trace_id_fkey" FOREIGN KEY ("trace_id") REFERENCES "public"."agent_traces" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table agent_task_checkpoints
-- ----------------------------
ALTER TABLE "public"."agent_task_checkpoints" ADD CONSTRAINT "agent_task_checkpoints_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "public"."agent_task_status" ("task_id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table agent_task_events
-- ----------------------------
ALTER TABLE "public"."agent_task_events" ADD CONSTRAINT "agent_task_events_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "public"."agent_task_status" ("task_id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table agent_task_status
-- ----------------------------
ALTER TABLE "public"."agent_task_status" ADD CONSTRAINT "agent_task_status_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table audit_results
-- ----------------------------
ALTER TABLE "public"."audit_results" ADD CONSTRAINT "audit_results_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "public"."audit_tasks" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table audit_tasks
-- ----------------------------
ALTER TABLE "public"."audit_tasks" ADD CONSTRAINT "audit_tasks_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table chat_messages
-- ----------------------------
ALTER TABLE "public"."chat_messages" ADD CONSTRAINT "chat_messages_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."chat_sessions" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table chat_sessions
-- ----------------------------
ALTER TABLE "public"."chat_sessions" ADD CONSTRAINT "chat_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table contract_clauses
-- ----------------------------
ALTER TABLE "public"."contract_clauses" ADD CONSTRAINT "contract_clauses_report_id_fkey" FOREIGN KEY ("report_id") REFERENCES "public"."contract_review_reports" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table contract_comparison_history
-- ----------------------------
ALTER TABLE "public"."contract_comparison_history" ADD CONSTRAINT "contract_comparison_history_contract1_id_fkey" FOREIGN KEY ("contract1_id") REFERENCES "public"."contract_review_reports" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."contract_comparison_history" ADD CONSTRAINT "contract_comparison_history_contract2_id_fkey" FOREIGN KEY ("contract2_id") REFERENCES "public"."contract_review_reports" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."contract_comparison_history" ADD CONSTRAINT "contract_comparison_history_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table contract_review_reports
-- ----------------------------
ALTER TABLE "public"."contract_review_reports" ADD CONSTRAINT "contract_review_reports_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table document_chunks
-- ----------------------------
ALTER TABLE "public"."document_chunks" ADD CONSTRAINT "document_chunks_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."documents" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table documents
-- ----------------------------
ALTER TABLE "public"."documents" ADD CONSTRAINT "documents_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table enrichment_jobs
-- ----------------------------
ALTER TABLE "public"."enrichment_jobs" ADD CONSTRAINT "enrichment_jobs_document_id_fkey" FOREIGN KEY ("document_id") REFERENCES "public"."documents" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table enterprise_policy_matches
-- ----------------------------
ALTER TABLE "public"."enterprise_policy_matches" ADD CONSTRAINT "enterprise_policy_matches_policy_id_fkey" FOREIGN KEY ("policy_id") REFERENCES "public"."policies" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table episodic_memories
-- ----------------------------
ALTER TABLE "public"."episodic_memories" ADD CONSTRAINT "episodic_memories_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."chat_sessions" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."episodic_memories" ADD CONSTRAINT "episodic_memories_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table failure_cases
-- ----------------------------
ALTER TABLE "public"."failure_cases" ADD CONSTRAINT "failure_cases_feedback_id_fkey" FOREIGN KEY ("feedback_id") REFERENCES "public"."user_feedback" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table financial_anomaly_records
-- ----------------------------
ALTER TABLE "public"."financial_anomaly_records" ADD CONSTRAINT "financial_anomaly_records_report_id_fkey" FOREIGN KEY ("report_id") REFERENCES "public"."financial_health_reports" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."financial_anomaly_records" ADD CONSTRAINT "financial_anomaly_records_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table financial_data_history
-- ----------------------------
ALTER TABLE "public"."financial_data_history" ADD CONSTRAINT "financial_data_history_financial_data_id_fkey" FOREIGN KEY ("financial_data_id") REFERENCES "public"."user_financial_data" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."financial_data_history" ADD CONSTRAINT "financial_data_history_modified_by_fkey" FOREIGN KEY ("modified_by") REFERENCES "public"."users" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table financial_health_reports
-- ----------------------------
ALTER TABLE "public"."financial_health_reports" ADD CONSTRAINT "financial_health_reports_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table financial_trend_data
-- ----------------------------
ALTER TABLE "public"."financial_trend_data" ADD CONSTRAINT "financial_trend_data_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table group_invitations
-- ----------------------------
ALTER TABLE "public"."group_invitations" ADD CONSTRAINT "group_invitations_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "public"."chat_groups" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table group_members
-- ----------------------------
ALTER TABLE "public"."group_members" ADD CONSTRAINT "group_members_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "public"."chat_groups" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table group_messages
-- ----------------------------
ALTER TABLE "public"."group_messages" ADD CONSTRAINT "group_messages_group_id_fkey" FOREIGN KEY ("group_id") REFERENCES "public"."chat_groups" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table improvement_records
-- ----------------------------
ALTER TABLE "public"."improvement_records" ADD CONSTRAINT "improvement_records_failure_case_id_fkey" FOREIGN KEY ("failure_case_id") REFERENCES "public"."failure_cases" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table invite_code_usages
-- ----------------------------
ALTER TABLE "public"."invite_code_usages" ADD CONSTRAINT "invite_code_usages_invite_code_id_fkey" FOREIGN KEY ("invite_code_id") REFERENCES "public"."invite_codes" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."invite_code_usages" ADD CONSTRAINT "invite_code_usages_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table invite_codes
-- ----------------------------
ALTER TABLE "public"."invite_codes" ADD CONSTRAINT "invite_codes_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table knowledge_bases
-- ----------------------------
ALTER TABLE "public"."knowledge_bases" ADD CONSTRAINT "knowledge_bases_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table multi_agent_intent_analyses
-- ----------------------------
ALTER TABLE "public"."multi_agent_intent_analyses" ADD CONSTRAINT "multi_agent_intent_analyses_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."multi_agent_sessions" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table multi_agent_reflection_records
-- ----------------------------
ALTER TABLE "public"."multi_agent_reflection_records" ADD CONSTRAINT "multi_agent_reflection_records_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."multi_agent_sessions" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table multi_agent_report_access_logs
-- ----------------------------
ALTER TABLE "public"."multi_agent_report_access_logs" ADD CONSTRAINT "multi_agent_report_access_logs_report_id_fkey" FOREIGN KEY ("report_id") REFERENCES "public"."multi_agent_reports" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."multi_agent_report_access_logs" ADD CONSTRAINT "multi_agent_report_access_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table multi_agent_report_versions
-- ----------------------------
ALTER TABLE "public"."multi_agent_report_versions" ADD CONSTRAINT "multi_agent_report_versions_report_id_fkey" FOREIGN KEY ("report_id") REFERENCES "public"."multi_agent_reports" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table multi_agent_reports
-- ----------------------------
ALTER TABLE "public"."multi_agent_reports" ADD CONSTRAINT "multi_agent_reports_parent_report_id_fkey" FOREIGN KEY ("parent_report_id") REFERENCES "public"."multi_agent_reports" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."multi_agent_reports" ADD CONSTRAINT "multi_agent_reports_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."multi_agent_sessions" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."multi_agent_reports" ADD CONSTRAINT "multi_agent_reports_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table multi_agent_sessions
-- ----------------------------
ALTER TABLE "public"."multi_agent_sessions" ADD CONSTRAINT "multi_agent_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table multi_agent_specialist_results
-- ----------------------------
ALTER TABLE "public"."multi_agent_specialist_results" ADD CONSTRAINT "multi_agent_specialist_results_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."multi_agent_sessions" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table policy_relations
-- ----------------------------
ALTER TABLE "public"."policy_relations" ADD CONSTRAINT "policy_relations_source_policy_id_fkey" FOREIGN KEY ("source_policy_id") REFERENCES "public"."policies" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."policy_relations" ADD CONSTRAINT "policy_relations_target_policy_id_fkey" FOREIGN KEY ("target_policy_id") REFERENCES "public"."policies" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table prompt_ab_tests
-- ----------------------------
ALTER TABLE "public"."prompt_ab_tests" ADD CONSTRAINT "prompt_ab_tests_template_a_id_fkey" FOREIGN KEY ("template_a_id") REFERENCES "public"."prompt_templates" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."prompt_ab_tests" ADD CONSTRAINT "prompt_ab_tests_template_b_id_fkey" FOREIGN KEY ("template_b_id") REFERENCES "public"."prompt_templates" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table prompt_executions
-- ----------------------------
ALTER TABLE "public"."prompt_executions" ADD CONSTRAINT "prompt_executions_template_id_fkey" FOREIGN KEY ("template_id") REFERENCES "public"."prompt_templates" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."prompt_executions" ADD CONSTRAINT "prompt_executions_trace_id_fkey" FOREIGN KEY ("trace_id") REFERENCES "public"."agent_traces" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table review_request_actions
-- ----------------------------
ALTER TABLE "public"."review_request_actions" ADD CONSTRAINT "review_request_actions_review_request_id_fkey" FOREIGN KEY ("review_request_id") REFERENCES "public"."review_requests" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table review_request_comments
-- ----------------------------
ALTER TABLE "public"."review_request_comments" ADD CONSTRAINT "review_request_comments_review_request_id_fkey" FOREIGN KEY ("review_request_id") REFERENCES "public"."review_requests" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table scheduled_tasks
-- ----------------------------
ALTER TABLE "public"."scheduled_tasks" ADD CONSTRAINT "fk_scheduled_tasks_user_id" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table system_logs
-- ----------------------------
ALTER TABLE "public"."system_logs" ADD CONSTRAINT "system_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table task_execution_logs
-- ----------------------------
ALTER TABLE "public"."task_execution_logs" ADD CONSTRAINT "fk_task_execution_logs_scheduled_task_id" FOREIGN KEY ("scheduled_task_id") REFERENCES "public"."scheduled_tasks" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."task_execution_logs" ADD CONSTRAINT "fk_task_execution_logs_user_id" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table task_notifications
-- ----------------------------
ALTER TABLE "public"."task_notifications" ADD CONSTRAINT "fk_task_notifications_execution_log_id" FOREIGN KEY ("execution_log_id") REFERENCES "public"."task_execution_logs" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."task_notifications" ADD CONSTRAINT "fk_task_notifications_task_id" FOREIGN KEY ("task_id") REFERENCES "public"."scheduled_tasks" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."task_notifications" ADD CONSTRAINT "fk_task_notifications_user_id" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table tax_report_documents
-- ----------------------------
ALTER TABLE "public"."tax_report_documents" ADD CONSTRAINT "tax_report_documents_tax_report_id_fkey" FOREIGN KEY ("tax_report_id") REFERENCES "public"."tax_reports" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table tax_reports
-- ----------------------------
ALTER TABLE "public"."tax_reports" ADD CONSTRAINT "tax_reports_audit_task_id_fkey" FOREIGN KEY ("audit_task_id") REFERENCES "public"."audit_tasks" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."tax_reports" ADD CONSTRAINT "tax_reports_review_request_id_fkey" FOREIGN KEY ("review_request_id") REFERENCES "public"."review_requests" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."tax_reports" ADD CONSTRAINT "tax_reports_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table tenant_audit_logs
-- ----------------------------
ALTER TABLE "public"."tenant_audit_logs" ADD CONSTRAINT "tenant_audit_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table tool_call_traces
-- ----------------------------
ALTER TABLE "public"."tool_call_traces" ADD CONSTRAINT "fk_tool_call_traces_session_id_chat_sessions" FOREIGN KEY ("session_id") REFERENCES "public"."chat_sessions" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."tool_call_traces" ADD CONSTRAINT "fk_tool_call_traces_user_id_users" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."tool_call_traces" ADD CONSTRAINT "tool_call_traces_parent_call_id_fkey" FOREIGN KEY ("parent_call_id") REFERENCES "public"."tool_call_traces" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
ALTER TABLE "public"."tool_call_traces" ADD CONSTRAINT "tool_call_traces_trace_id_fkey" FOREIGN KEY ("trace_id") REFERENCES "public"."agent_traces" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table user_action_logs
-- ----------------------------
ALTER TABLE "public"."user_action_logs" ADD CONSTRAINT "user_action_logs_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table user_feedback
-- ----------------------------
ALTER TABLE "public"."user_feedback" ADD CONSTRAINT "user_feedback_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table user_financial_data
-- ----------------------------
ALTER TABLE "public"."user_financial_data" ADD CONSTRAINT "user_financial_data_reviewed_by_fkey" FOREIGN KEY ("reviewed_by") REFERENCES "public"."users" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."user_financial_data" ADD CONSTRAINT "user_financial_data_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table workflow_node_executions
-- ----------------------------
ALTER TABLE "public"."workflow_node_executions" ADD CONSTRAINT "fk_workflow_node_executions_agent" FOREIGN KEY ("agent_trace_id") REFERENCES "public"."agent_traces" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."workflow_node_executions" ADD CONSTRAINT "fk_workflow_node_executions_trace" FOREIGN KEY ("workflow_trace_id") REFERENCES "public"."workflow_traces" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table workflow_traces
-- ----------------------------
ALTER TABLE "public"."workflow_traces" ADD CONSTRAINT "fk_workflow_traces_human_review" FOREIGN KEY ("human_review_id") REFERENCES "public"."review_requests" ("id") ON DELETE SET NULL ON UPDATE NO ACTION;
ALTER TABLE "public"."workflow_traces" ADD CONSTRAINT "fk_workflow_traces_session" FOREIGN KEY ("session_id") REFERENCES "public"."chat_sessions" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
