FROM python:3.10.0-alpine

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --upgrade pip
RUN pip install mkdocs-material==9.5.5 mkdocs-glightbox

WORKDIR /Notes

COPY overrides ./build/overrides

COPY docs ./build/docs
COPY mkdocs-docker.yml mkdocs.yml
RUN mkdocs build -f mkdocs.yml

WORKDIR /Notes/site
EXPOSE 8000
CMD ["python", "-m", "http.server", "8000"]
