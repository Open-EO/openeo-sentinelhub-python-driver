# Python

This project needs **Python 3.6** to run properly (might change, please check `python_version` in `./rest/Pipfile`).

## Linux

### Installing Python 3.6

If you don't have the right Python version installed follow instructions below (or your way):

- You will probably need to install Python 3.6 from a ppa repository which isn't included in your Linux distro's ppa list by default. Run these commands:

```bash
$ sudo add-apt-repository ppa:deadsnakes/ppa
$ sudo apt update
$ sudo apt install python3.6
```

Check which aliases are in use for Python:

```bash
$ ls -l /usr/bin/python*
```

If Python 3.6 is installed and added to the path, the following should start Python 3.6 CLI

```bash
$ python3.6
Python 3.6.12 (default, Aug 17 2020, 23:45:20) 
[GCC 9.3.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>>
```

(source: [tecmint's article about installing Python 3.6 from a ppa](https://www.tecmint.com/install-python-in-ubuntu/))

### Managing multiple Python versions 

Managing and using multiple Python versions with [`update-alternatives`](https://linux.die.net/man/8/update-alternatives), so you don't have to remove the current Python version.

- list python alternatives

```bash
$ update-alternatives --list python
```

- add Python 3.6 as the alternative 1 (alternative 0 is the default choice)

```bash
$ update-alternatives --install /usr/bin/python python /usr/bin/python3.6 1
```

- add any other Python version as an alternative 2 (and 3, etc.)

```bash
$ update-alternatives --install /usr/bin/python python /usr/bin/python3.8 2
```

- select a version you want to use currently

```bash
$ update-alternatives --config python
There are 2 choices for the alternative python (providing /usr/bin/python).

  Selection    Path                      Priority   Status
------------------------------------------------------------
* 0            /usr/local/bin/python3.8   2         auto mode
  1            /usr/bin/python3.6         1         manual mode
  2            /usr/local/bin/python3.8   2         manual mode

Press <enter> to keep the current choice[*], or type selection number: 
```

(source: [hackersandslackers's article about managing multiple Python versions in Ubuntu](https://hackersandslackers.com/multiple-versions-python-ubuntu/))

## Windows

- [latest Python 3.6.x for Windows](https://www.python.org/downloads/release/python-368/)
  - Click `Disable path length limit` in the last step of installer to avoid problems