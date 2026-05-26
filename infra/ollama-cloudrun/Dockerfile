# Private Ollama instance for entity tagging on Cloud Run (GPU)
# Deploy: gcloud run deploy ollama --source=. --gpu=1 --gpu-type=nvidia-l4 \
#          --memory=16Gi --cpu=4 --max-instances=1 --no-allow-unauthenticated \
#          --project=location-19291 --region=us-central1

FROM ollama/ollama:latest

# Pre-pull the model at build time so cold starts are fast
RUN ollama serve & sleep 5 && ollama pull phi3:mini && pkill ollama

EXPOSE 11434

ENTRYPOINT ["ollama", "serve"]
