from ._common import ProcessEOTask
import process

class productEOTask(ProcessEOTask):
    """
        This process is an exact alias for the multiply process. See process.multiply.multiplyEOTask.
    """
    def process(self, arguments):
        return process.multiply.multiplyEOTask(self._arguments, self.job_id, self.logger, self._variables).process(arguments)