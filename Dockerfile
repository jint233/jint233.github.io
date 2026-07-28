FROM python:3.10.0-alpine

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG MODULES=all
ARG JOBS=auto

WORKDIR /Notes

COPY requirements.txt ./
RUN apk add --no-cache rsync \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY mkdocs.yml ./
COPY scripts ./scripts
COPY overrides ./overrides
COPY docs ./docs
RUN JOBS="$JOBS" ./scripts/build-modules.sh "$MODULES"

WORKDIR /Notes/site
EXPOSE 8000
CMD ["python", "../scripts/preview.py", "--bind", "0.0.0.0", "--port", "8000", "--directory", "."]
