from enum import Enum

from sentinelhub import BatchRequestStatus, BatchUserAction


class openEOBatchJobStatus(Enum):
    CREATED = "created"
    QUEUED = "queued"
    CANCELED = "canceled"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"

    @staticmethod
    def from_sentinelhub_batch_job_status(sentinelhub_batch_job_status, sentinelhub_batch_user_action):
        conversion_table = {
            BatchRequestStatus.CREATED: openEOBatchJobStatus.CREATED,
            BatchRequestStatus.ANALYSING: openEOBatchJobStatus.CREATED,
            BatchRequestStatus.ANALYSIS_DONE: openEOBatchJobStatus.CREATED,
            BatchRequestStatus.PROCESSING: openEOBatchJobStatus.RUNNING,
            BatchRequestStatus.DONE: openEOBatchJobStatus.FINISHED,
            BatchRequestStatus.FAILED: openEOBatchJobStatus.ERROR,
            BatchRequestStatus.PARTIAL: openEOBatchJobStatus.ERROR,
            BatchRequestStatus.CANCELED: openEOBatchJobStatus.CANCELED,
        }
        if sentinelhub_batch_user_action == BatchUserAction.START:
            return openEOBatchJobStatus.QUEUED
        return conversion_table.get(sentinelhub_batch_job_status)
