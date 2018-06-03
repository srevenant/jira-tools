FROM python:3

WORKDIR /app
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt
COPY jira* /app/

