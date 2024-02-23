FROM python:3.11-slim

WORKDIR /usr/src/app

COPY . /usr/src/app
RUN pip install --no-cache-dir .

USER 1001

CMD ["sc2sceneswitcher"]
