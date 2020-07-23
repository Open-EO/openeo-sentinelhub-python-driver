import os
import multiprocessing
import queue
import time
import signal
import time
import json
import logging
import resource
import beeline
import psutil


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


# application performance monitoring:
HONEYCOMP_APM_API_KEY = os.environ.get('HONEYCOMP_APM_API_KEY')
beeline_client = None
if HONEYCOMP_APM_API_KEY:
    beeline.init(writekey=HONEYCOMP_APM_API_KEY, dataset='OpenEO - workers', service_name='OpenEO')
    beeline_client = beeline.get_beeline().client


def _feed_monitoring_system():
    if not HONEYCOMP_APM_API_KEY:
        return

    # https://docs.python.org/3/library/resource.html
    rusage_parent = resource.getrusage(resource.RUSAGE_SELF)
    rusage_children = resource.getrusage(resource.RUSAGE_CHILDREN)
    metric_peak_memory = (rusage_parent.ru_maxrss + rusage_children.ru_maxrss) * resource.getpagesize()

    metric_cpu = psutil.cpu_percent()

    mem = psutil.virtual_memory()
    # - total: total physical memory.
    # - available: the memory that can be given instantly to processes without the system going into
    #   swap. This is calculated by summing different memory values depending on the platform and it
    #   is supposed to be used to monitor actual memory usage in a cross platform fashion.
    # Note that mem.used is not a good metric for us:
    # - used: memory used, calculated differently depending on the platform and designed for informational
    #   purposes only. `total - free` does not necessarily match used.
    metric_used_mem = mem.total - mem.free

    ev = beeline_client.new_event()
    ev.add({
        'peak_mem': metric_peak_memory,
        'cpu': metric_cpu,
        'used_mem': metric_used_mem,
    })
    ev.send()


def main():
    # create workers:
    jobs_queue = multiprocessing.Queue()
    processes = []
    for i in range(10):
        p = multiprocessing.Process(target=worker_proc, args=(jobs_queue, i,))
        p.daemon = True
        p.start()
        processes.append(p)

    # listen for changes on DynamoDB jobs table and dispatch any new jobs to
    # the workers:
    running_jobs = set()
    try:
        while True:
            _feed_monitoring_system()

            # Because we couldn't find a way to get notifications about DynamoDB changes (via Streams)
            # without polling, we use SQS to be notified when new jobs surface. We still query DynamoDB
            # to get them though, even though we receive the job_ids:
            logger.info("Sleeping / waiting for wakeup:")
            wakeup = JobsPersistence.wait_for_wakeup(timeout=20)
            if not wakeup:
                logger.info("Continue sleeping...")
                continue

            logger.info("Woke up!")
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
                        'process_graph': json.loads(job["process"]['S'])["process_graph"],
                        'variables': json.loads(job["variables"]['S']) if "variables" in job else {},
                    })

            # GET queued AND should_be_cancelled = True
            cancelled_queued = JobsPersistence.query_cancelled_queued()
            for page in cancelled_queued:
                for job in page["Items"]:
                    # Set them back to created:
                    job_id = job["id"]['S']
                    JobsPersistence.update_cancelled_queued_to_created(job_id)

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


    except KeyboardInterrupt:
        logger.info("SIGINT received, exiting.")


    # clean up and quit:
    for i in range(len(processes)):
        jobs_queue.put(SIGNAL_QUIT_JOB)
    for p in processes:
        p.join()

if __name__ == "__main__":
    main()