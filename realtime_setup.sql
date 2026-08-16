-- 1. Enable realtime for the job status channel
INSERT INTO realtime.channels (pattern, description, enabled)
VALUES ('job:%', 'Live updates for background download jobs', true)
ON CONFLICT (pattern) DO UPDATE
SET description = EXCLUDED.description,
    enabled = EXCLUDED.enabled;

-- 2. Create the notification function for jobs table
CREATE OR REPLACE FUNCTION public.notify_job_status()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM realtime.publish(
    'job:' || NEW.id::text,
    'status_changed',
    to_jsonb(NEW)
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 3. Drop existing trigger if it exists
DROP TRIGGER IF EXISTS job_status_trigger ON public.jobs;

-- 4. Create the trigger to publish changes
CREATE TRIGGER job_status_trigger
AFTER UPDATE ON public.jobs
FOR EACH ROW
WHEN (OLD.progress IS DISTINCT FROM NEW.progress OR OLD.status IS DISTINCT FROM NEW.status OR OLD.stage IS DISTINCT FROM NEW.stage)
EXECUTE FUNCTION public.notify_job_status();
