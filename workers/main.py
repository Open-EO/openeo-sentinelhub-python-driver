import multiprocessing
import queue
import time
import signal
import time
import json
import logging


from dotenv import load_dotenv
load_dotenv(verbose=True)


from dynamodb import JobsPersistence
from worker import worker_proc, SIGNAL_QUIT_JOB


logger = multiprocessing.get_logger()
for handler in logger.handlers:
    logger.removeHandler(handler)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(logging.Formatter('%(asctime)s [%(processName)s] %(levelname)s %(message)s'))
logger.addHandler(ch)


# when running inside docker, the default SIGINT signal handler is not installed,
# so the KeyboardInterrupt is not triggered. This should install it manually:
#   https://stackoverflow.com/a/40785230
signal.signal(signal.SIGINT, signal.default_int_handler)


def main():
    # create workers:
    jobs_queue = multiprocessing.Queue()
    results_queue = multiprocessing.Queue()
    processes = []
    for i in range(10):
        p = multiprocessing.Process(target=worker_proc, args=(jobs_queue, results_queue, i,))
        p.daemon = True
        p.start()
        processes.append(p)

    # listen for changes on DynamoDB jobs table and dispatch any new jobs to
    # the workers:
    running_jobs = set()
    try:
        while True:
            # Because we couldn't find a way to get notifications about DynamoDB changes (via Streams)
            # without polling, we simply poll the DynamoDB directly instead:
            # GET queued AND should_be_cancelled = False
            new_queued = JobsPersistence.query_new_queued()
            for page in new_queued:
                for job in page["Items"]:
                    job_id = job["id"]['S']
                    logger.info("Found a job: {}".format(job_id))

                    success = JobsPersistence.update_queued_to_running(job_id)
                    if not success:
                        # someone was faster than us - we were not able to mark it as running,
                        # so we shouldn't execute it:
                        logger.info("Found a job, but could not update its status to running... ignoring it.")
                        continue

                    running_jobs.add(job_id)
                    jobs_queue.put({
                        'job_id': job_id,
                        'process_graph': json.loads(job["process_graph"]['S']),
                        'variables': json.loads(job["variables"]['S']) if "variables" in job else {},
                    })

            # GET queued AND should_be_cancelled = True
            cancelled_queued = JobsPersistence.query_cancelled_queued()
            for page in cancelled_queued:
                for job in page["Items"]:
                    # Set them back to submitted:
                    job_id = job["id"]['S']
                    JobsPersistence.update_cancelled_queued_to_submitted(job_id)

            # GET running AND should_be_cancelled = True
            cancelled_running = JobsPersistence.query_cancelled_running()
            for page in cancelled_running:
                for job in page["Items"]:
                    job_id = job["id"]['S']
                    if job_id not in running_jobs:
                        continue

                    JobsPersistence.update_cancelled_running_to_canceled(job_id)
                    # we don't actually kill the process (though that would be nice), we just mark that the
                    # job is no longer running, so the results will not be used:
                    running_jobs.remove(job_id)

            logger.info("Sleeping...")
            time.sleep(5)

            # write results:
            while True:
                try:
                    job_id, results, error_msg, error_code, http_code = results_queue.get(False)
                except queue.Empty:
                    break
                try:
                    JobsPersistence.update_running_to_finished(job_id, results, error_msg, error_code, http_code)
                    logger.info("Job {} finished.".format(job_id))
                except:
                    logger.exception("Unknown error saving results, job will hang indefinitely! {}".format(job_id))

    except KeyboardInterrupt:
        logger.info("SIGINT received, exiting.")


    # clean up and quit:
    for i in range(len(processes)):
        jobs_queue.put(SIGNAL_QUIT_JOB)
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()