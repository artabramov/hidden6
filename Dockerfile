FROM python:3.12-slim
WORKDIR /opt/hidden

RUN apt-get update \
 && apt-get install -y --no-install-recommends gocryptfs fuse3 \
 && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir -r requirements.txt \
 && ln -s /opt/hidden/bin/hiddenctl /usr/local/bin/hiddenctl

ENTRYPOINT ["./entrypoint.sh"]
