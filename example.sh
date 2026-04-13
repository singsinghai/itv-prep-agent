docker build -t itv-prep-agent .
docker run --rm -p 8080:8080 --env-file .env itv-prep-agent