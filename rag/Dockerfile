# ai-generated: 0% - the course's Dockerfile, unchanged
# The rag service (AI-SPEC.md A-06). Built from the repository root, not from rag/:
#
#   rag:
#     build: {context: ., dockerfile: rag/Dockerfile}
#
# because the corpus is documents of the whole repository, named by their repository paths in rag/corpus.yaml
# (A-04), and the image carries them: the checker starts the service with no bind mount, as in every lab. So a
# change to a document or to rag/corpus.yaml reaches the service only through a rebuild:
# `docker compose up -d --build rag`, then `POST /index`.
FROM python:3.13-slim
WORKDIR /app
COPY rag/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY rag/ /app/
# The repository as data, read by POST /index. rag/Dockerfile.dockerignore keeps .git, data/ and the like out.
COPY . /repo/
ENV RAG_REPO=/repo PYTHONUNBUFFERED=1
USER 65534:65534
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
