from ._common import ProcessEOTask, ProcessArgumentInvalid, ProcessArgumentRequired
from eolearn.core import EOWorkflow
import process

class reduceEOTask(ProcessEOTask):
    def generate_workflow_dependencies(self, graph, parent_arguments):
        result_task = None
        # input_args = {}
        tasks = {}

        print(">>>>>>>>>>>>>>>>>>>>>>>> graph:\n")
        print(graph)
        print("\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")

        for node_name, node_definition in graph.items():
            print(">>>>>>>>>>>>>>>>>>   NODE NAME: " + node_name)
            node_arguments = node_definition["arguments"]

            for argument in node_arguments:
                print(">>>>>>>>>>>>>>>>>>   ARGUMENT: " + argument)
                if isinstance(node_arguments[argument],dict):
                    print(argument)
                    for key in node_arguments[argument]:
                        if key == "from_argument":
                            node_arguments[argument] = parent_arguments[node_arguments[argument][key]]
                            print(">>>>>>>>>>>>>>>>>> setting from argument\n")
                            print(node_arguments)
                            print("<<<<<<<<<<<<<<<<<<\n")

                # input_args[node_name] = node_arguments

            #initialise instance of clas and put it in a task
            class_name = node_definition["process_id"] + "EOTask"
            print(">>>>>>>>>>>>>>>>>>>>>>>>")
            print(getattr(getattr(process,node_definition["process_id"]), class_name))
            class_obj = getattr(getattr(process,node_definition["process_id"]), class_name)

            tasks[node_name] = class_obj(node_arguments, "some_job_id", None)

            if node_definition.get('result', False):
                result_task = tasks[node_name]

        print(">>>>>>>>>>>>>>>>>>>>>>>> tasks:")
        print(tasks)
        print("<<<<<<<<<<<<<<<<<<<<<<<<")
        dependencies = []
        for node_name, task in tasks.items():
            depends_on = [tasks[x] for x in task.depends_on()]
            dependencies.append((task, depends_on, 'Node name: ' + node_name))

        return dependencies, result_task


    def process(self, arguments):
        print(">>>>>>>>>>>>>>>>>>>>>>>> ARGUMENTS:\n")
        print(arguments)
        print("\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        try:
            data = arguments["data"]
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'data'.")

        try:
            dimension = arguments["dimension"]

            if dimension not in data.dims:
                raise ProcessArgumentInvalid("The argument 'dimension' in process 'reduce' is invalid: Dimension '{}' does not exist in data.".format(dimension))
        except:
            raise ProcessArgumentRequired("Process 'reduce' requires argument 'dimension'.")

        reducer = arguments.get("reducer")
        target_dimension = arguments.get("target_dimension")
        binary = arguments.get("binary", False)

        if reducer is None:
            if data[dimension].size > 1:
                raise ProcessArgumentInvalid("The argument 'dimension' in process 'reduce' is invalid: Dimension '{}' has more than one value, but reducer is not specified.".format(dimension))
            return data.squeeze(dimension, drop=True)
        else:
            dependencies, result_task = self.generate_workflow_dependencies(reducer["callback"], arguments)
            print(">>>>>>>>>>>>>>>>>>>> dependencies:\n")
            print(dependencies)
            print("\n<<<<<<<<<<<<<<<<<<<<")
            workflow = EOWorkflow(dependencies)
            workflow.execute({})
            return result_task.results

        # return result
