# Cloud Run Deployment Guide

This guide explains how to deploy the ZScribe Intake Agent to Google Cloud Run.

## Architecture

The deployment consists of **TWO separate Cloud Run services**:

1. **data-api** - Serves template, patient, and organization data (api_server.py)
2. **intake-agent** - Runs both the intake API and the LiveKit calling agent worker

## Prerequisites

1. Google Cloud Project with billing enabled
2. gcloud CLI installed and authenticated
3. Cloud Run API enabled
4. Artifact Registry API enabled (for storing Docker images)

## Environment Variables Required

### For `data-api` service:
- `PORT` (automatically set by Cloud Run to 8080)
- `SUPABASE_URL`
- `SUPABASE_KEY`

### For `intake-agent` service:
- `PORT` (automatically set by Cloud Run to 8080)
- `API_BASE_URL` (URL of the data-api service)
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `SIP_OUTBOUND_TRUNK_ID`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `LANGFUSE_SECRET_KEY` or `INTAKE_LANGFUSE_SECRET_KEY`
- `LANGFUSE_PUBLIC_KEY` or `INTAKE_LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_HOST` or `INTAKE_LANGFUSE_HOST`

## Deployment Steps

### Step 1: Deploy data-api Service

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="us-central1"

# Build and deploy data-api
gcloud run deploy data-api \
  --source . \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="SUPABASE_URL=your-supabase-url,SUPABASE_KEY=your-supabase-key" \
  --min-instances=0 \
  --max-instances=10 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300
```

**Note the data-api URL** from the deployment output (e.g., `https://data-api-xxx.run.app`)

### Step 2: Deploy intake-agent Service

```bash
# Get the data-api URL from step 1
export DATA_API_URL="https://data-api-xxx.run.app"

# Deploy intake-agent
gcloud run deploy intake-agent \
  --source . \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="API_BASE_URL=$DATA_API_URL,LIVEKIT_URL=wss://your-livekit-url,LIVEKIT_API_KEY=your-key,LIVEKIT_API_SECRET=your-secret,SIP_OUTBOUND_TRUNK_ID=ST_xxx,SUPABASE_URL=your-supabase-url,SUPABASE_KEY=your-supabase-key,LANGFUSE_SECRET_KEY=your-key,LANGFUSE_PUBLIC_KEY=your-key,LANGFUSE_HOST=https://cloud.langfuse.com" \
  --min-instances=1 \
  --max-instances=10 \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600 \
  --concurrency=80
```

**Important:** `intake-agent` needs `--min-instances=1` to keep the LiveKit worker always running!

### Step 3: Test the Deployment

```bash
# Get the intake-agent URL
export INTAKE_URL=$(gcloud run services describe intake-agent --region=$REGION --format='value(status.url)')

# Test health endpoint
curl $INTAKE_URL/health

# Test making a call
curl -X POST $INTAKE_URL/intake-calls \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "+1234567890",
    "template_id": "your-template-id",
    "organization_id": "your-org-id",
    "patient_id": "your-patient-id",
    "intake_id": "your-intake-id"
  }'
```

## Alternative: Deploy Using Dockerfile Directly

If you prefer to build the Docker image manually:

```bash
# Build the Docker image
docker build -t gcr.io/$PROJECT_ID/intake-agent:latest .

# Push to Google Container Registry
docker push gcr.io/$PROJECT_ID/intake-agent:latest

# Deploy from the image
gcloud run deploy intake-agent \
  --image=gcr.io/$PROJECT_ID/intake-agent:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars="..." \
  --min-instances=1
```

## Monitoring

View logs:
```bash
# intake-agent logs
gcloud run services logs read intake-agent --region=$REGION --limit=50

# data-api logs
gcloud run services logs read data-api --region=$REGION --limit=50
```

## Cost Optimization

- **data-api**: Set `--min-instances=0` to scale to zero when not in use
- **intake-agent**: Must keep `--min-instances=1` so the LiveKit worker is always listening for dispatches

## Troubleshooting

### Worker not picking up dispatches
- Check that LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET are correct
- Check logs to see if the worker started: `gcloud run services logs read intake-agent --region=$REGION`
- Ensure `--min-instances=1` is set

### API can't reach data-api
- Check that API_BASE_URL is set to the correct data-api URL
- Verify data-api is deployed and accessible

### Port issues
- Cloud Run automatically sets PORT=8080
- Don't override it - let Cloud Run manage it
