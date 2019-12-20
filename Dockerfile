FROM python:3.7

WORKDIR /app

EXPOSE 8000

RUN apt-get update && \
    apt-get install -y libwebp-dev && \
    apt-get clean

RUN pip install --no-cache-dir \
    imagehash \
    redlock-py \
    uvicorn \
    fastapi \
    numpy \
    pillow \
    requests \
    prometheus_client \
    python-multipart

COPY . .

CMD ["uvicorn","nemivir.service.image_api:app","--host","0.0.0.0"]