# Jira Tools

Random tools leveraging the Jira SDK (python)

## configuring

* Copy `config.py.example` into `config.py` and edit to suite

## demo

You can try stuff out using docker:

* docker build -t jiratools .
* docker run -it --rm --volume "$(pwd):/app/" jiratools  /bin/bash
