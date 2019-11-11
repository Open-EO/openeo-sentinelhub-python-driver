import signal
import logging
import sys
import multiprocessing
from eolearn.core import EOWorkflow


import process
from dynamodb import JobsPersistence


# logger = multiprocessing.get_logger()
logger = multiprocessing.log_to_stderr()
logger.setLevel(logging.DEBUG)


SIGNAL_QUIT_JOB = "QUIT"


def _execute_process_graph(process_graph, job_id, variables):
    # This is what we are aiming for:
    #
    #   loadco1 = load_collectionEOTask(process_graph["loadco1"]["arguments"])
    #   ndvi1 = ndviEOTask(process_graph["ndvi1"]["arguments"])
    #   reduce1 = reduceEOTask(process_graph["reduce1"]["arguments"])
    #   tasks = [
    #       (loadco1, [], "Node name: load1"),
    #       (ndvi1, [loadco1], "Node name: ndvi1"),
    #       (reduce1, [ndvi1], "Node name: reduce1"),
    #   ]
    #
    #   workflow = EOWorkflow(tasks)
    #   workflow.execute({})


    # first create all the tasks and remember their names, so we will be able
    # to reference them when looking for tasks that current task depends on:
    tasks_by_name = {}
    result_task = None
    for node_name, node_definition in process_graph.items():
        # We would like to instantiate an appropriate EOTask based on
        # process_id, like this:
        #   tasks_by_name[node_name] = \
        #           load_collectionEOTask(node_definition['arguments'])
        process_id = node_definition['process_id']
        task_module_name = '{process_id}'.format(process_id=process_id)
        task_class_name = '{process_id}EOTask'.format(process_id=process_id)
        task_module = getattr(sys.modules[__name__].process, task_module_name)
        task_class = getattr(task_module, task_class_name)
        tasks_by_name[node_name] = task_class(node_definition['arguments'], job_id, logger, variables)

        if node_definition.get('result', False):
            result_task = tasks_by_name[node_name]
            if process_id != 'save_result':
                raise process.VariableValueMissing("No value specified for process graph variable 'save_result'.")


    # create a list of tasks for workflow:
    tasks = []
    for node_name, task in tasks_by_name.items():
        depends_on = [tasks_by_name[x] for x in task.depends_on()]
        tasks.append((task, depends_on, 'Node name: ' + node_name))


    workflow = EOWorkflow(tasks)

    logger.debug("[{}]: executing workflow...".format(job_id))
    result = workflow.execute({})
    logger.debug("[{}]: workflow executed.".format(job_id))

    return result_task.results


def worker_proc(jobs_queue, worker_number):
    # worker shouldn't be concerned with signals - parent orchestrates
    # everything and will tell us if we need to quit:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    while True:
        job = jobs_queue.get(True, None)
        logger.info("Worker {} received a job [{}]: {}".format(worker_number, job["job_id"], job))
        if job == SIGNAL_QUIT_JOB:
            return

        # try to execute job's process graph:
        results = None
        error_msg = None
        error_code = None
        http_code = None
        try:
            results = _execute_process_graph(job["process_graph"], job["job_id"], job["variables"])
            logger.info("Worker {} successfully finished job [{}]".format(worker_number, job["job_id"]))
        except Exception as ex:
            logger.exception("Worker {}, job [{}] exec failed: {}".format(worker_number, job["job_id"], str(ex)))
            error_msg = ex.msg if hasattr(ex, "msg") else str(ex)
            error_code = ex.error_code if hasattr(ex, "error_code") else "Internal"
            http_code = ex.http_code if hasattr(ex, "http_code") else 500
        finally:
            job_id = job["job_id"]
            logger.info("Worker {} writing results for job [{}]".format(worker_number, job_id))

            # write results:
            try:
                JobsPersistence.update_running_to_finished(job_id, results, error_msg, error_code, http_code)
                logger.info("Job {} finished.".format(job_id))
            except:
                logger.exception("Unknown error saving results, job will hang indefinitely! {}".format(job_id))
