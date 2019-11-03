# Clinic Simulation Project

Install Repo:
Go to directory where you want to install the project (i.e. `cd <dirName>`)
`git clone`
`cd`

Install Anaconda:
`conda create --name clinic-simulation python=3.6`
`conda activate clinic-simulation`
`conda env update --file env.yaml` (this will also be used to update our env as new dep are added)

In VSCode make sure you interpreter is set to clinic-simulation:

- install Python for vscode: View > Extensions > search for Python
- CMD + SHIFT + P > select python interpreter
  Check by running `python --version` and make sure it is Python 3.6

When we are adding new dep in python:
`conda install <thing>`
`conda env export > env.yaml`

Run project:
`python <file-name>`
