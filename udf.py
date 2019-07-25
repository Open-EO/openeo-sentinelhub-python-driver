import subprocess

def execute_udf(data):
	# save code to .py file
	# run docker container with installed python which calls that.py file
	out = subprocess.check_output(['docker', 'run', '-d', '--name', CONTAINER_NAME, IMAGE_NAME])
