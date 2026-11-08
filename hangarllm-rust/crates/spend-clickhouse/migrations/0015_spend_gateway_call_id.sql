ALTER TABLE {database}.spend_logs
    ADD COLUMN IF NOT EXISTS hangarllm_call_id String DEFAULT '' AFTER response_id,
    ADD INDEX IF NOT EXISTS idx_hangarllm_call_id hangarllm_call_id
        TYPE bloom_filter(0.001) GRANULARITY 1,
    ADD INDEX IF NOT EXISTS idx_request_id request_id
        TYPE bloom_filter(0.001) GRANULARITY 1
