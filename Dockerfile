# 신문 사설 모음 - Synology NAS / Docker 배포용
FROM python:3.12-slim

WORKDIR /app

# 의존성만 먼저 설치 (캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY app ./app
COPY templates ./templates

# 데이터 디렉터리 (볼륨 마운트 지점)
RUN mkdir -p /app/data

EXPOSE 8000

# Railway 등은 실행 시 PORT를 지정하므로, 셸에서 읽도록 함
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
