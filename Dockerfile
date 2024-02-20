FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get -y upgrade && \
    apt-get install -y curl python3.10-full alsa-base alsa-utils ffmpeg

# Default python3-pip installs python3.8 and links pip to it.
WORKDIR /tmp
RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && python3.10 get-pip.py
COPY app/requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

WORKDIR /app

CMD ["python3", "entry.py"]
