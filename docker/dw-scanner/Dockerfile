# syntax=docker/dockerfile:1
FROM ubuntu:18.04
COPY . /app
RUN apt-get update \
  && apt-get install -y python3-pip python3-dev masscan \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip
RUN pip3 install kafka-python 
RUN pip3 install pyyaml
RUN pip3 install tinydb
CMD ["python3","-u","/app/scanner.py"]
