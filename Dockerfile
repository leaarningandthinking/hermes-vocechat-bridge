FROM python:3.11-slim

LABEL maintainer="your-github-username"
LABEL description="Bridge between VoceChat and Hermes Agent"

WORKDIR /app

COPY bridge.py .
COPY config.yaml.example .

EXPOSE 8010

CMD ["python3", "bridge.py"]
