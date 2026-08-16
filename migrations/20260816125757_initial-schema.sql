CREATE TABLE jobs (
    id VARCHAR(36) PRIMARY KEY,
    source_url TEXT NOT NULL,
    provider VARCHAR(64),
    title TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    progress FLOAT DEFAULT 0.0,
    speed VARCHAR(64),
    eta VARCHAR(64),
    stage VARCHAR(64),
    format_id VARCHAR(128),
    output_format VARCHAR(32),
    quality VARCHAR(32),
    filename TEXT,
    file_path TEXT,
    file_size BIGINT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    expires_at TIMESTAMP,
    error_message TEXT,
    error_category VARCHAR(64),
    celery_task_id VARCHAR(128)
);

CREATE INDEX idx_jobs_status ON jobs(status);

CREATE TABLE download_history (
    id VARCHAR(36) PRIMARY KEY,
    job_id VARCHAR(36) NOT NULL,
    source_url TEXT NOT NULL,
    provider VARCHAR(64),
    title TEXT,
    output_format VARCHAR(32),
    file_size BIGINT,
    status VARCHAR(32) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_download_history_job_id ON download_history(job_id);


