# Cloud Run Deployment Guide - Intake Agent Worker

## Overview
This guide documents the successful deployment of the LiveKit intake agent worker to Google Cloud Run. Use this as a reference for future deployments and troubleshooting.

**Last Updated**: December 2, 2025
**Current Stable Version**: intake-worker-v2
**Service URL**: https://intake-worker-v2-292492747795.us-central1.run.app

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Project Structure](#project-structure)
3. [Docker Build Process](#docker-build-process)
4. [Cloud Run Deployment](#cloud-run-deployment)
5. [Environment Variables](#environment-variables)
6. [Critical Configuration](#critical-configuration)
7. [Troubleshooting](#troubleshooting)
8. [Deployment Checklist](#deployment-checklist)

---

## Prerequisites

### Required Tools
- Docker Desktop (for Windows)
- Google Cloud SDK (`gcloud` CLI)
- Git
- Python 3.11

### GCP Setup
- **Project ID**: `zscribe`
- **Region**: `us-central1`
- **Artifact Registry Repository**: `intake-agent`
- **Service Account**: Default compute service account

### Authentication
```bash
# Login to Google Cloud
gcloud auth login

# Set project
gcloud config set project zscribe

# Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## Project Structure

```
intake_agent/
├── src/
│   ├── calling_agent.py       # Main agent logic
│   ├── worker_server.py       # Worker + health check server
│   ├── api_client.py          # API utilities
│   ├── prompts.py             # Prompt management
│   └── download_models.py     # Model pre-download script
├── Dockerfile.worker          # Worker service Dockerfile
├── pyproject.toml            # Python dependencies
├── .env                      # Local environment variables
└── .dockerignore             # Docker ignore patterns
```

---

## Docker Build Process

### Dockerfile.worker Configuration

**Location**: `Dockerfile.worker`

```dockerfile
# Base image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy source files
COPY src/ ./src/

# Download models during build (prevents slow cold starts)
RUN python src/download_models.py download-files || echo "Model download completed with warnings (expected for some models)"

# Set environment variables for model caching
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV HF_HUB_CACHE=/tmp/.cache/huggingface
ENV TRANSFORMERS_CACHE=/tmp/.cache/transformers

# Expose port for health checks
EXPOSE 8080

# Run worker_server (includes both worker and health check HTTP server)
CMD ["python", "src/worker_server.py"]
```

### Build Commands

#### For intake-worker-v2 (Current Production)

```bash
# Build the image
docker build -f Dockerfile.worker -t us-central1-docker.pkg.dev/zscribe/intake-agent/intake-worker-v2:latest .

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/zscribe/intake-agent/intake-worker-v2:latest
```

**Build Time**: ~2-3 minutes
**Image Size**: ~300 MB

### Key Build Steps
1. ✅ Base Python 3.11 slim image
2. ✅ Install system dependencies (gcc, g++, make)
3. ✅ Install Python packages from pyproject.toml
4. ✅ Copy source code
5. ✅ **Download models during build** (critical for performance)
6. ✅ Set environment variables
7. ✅ Configure entry point

---

## Cloud Run Deployment

### Working Deployment Configuration

#### Service: `intake-worker-v2` (Production - CURRENT)

**Last Deployed**: December 2, 2025 at 13:10 UTC
**Revision**: intake-worker-v2-00001-sw9
**Status**: ✅ Active and Registered with LiveKit

```bash
gcloud run deploy intake-worker-v2 \
  --image us-central1-docker.pkg.dev/zscribe/intake-agent/intake-worker-v2:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "LIVEKIT_URL=wss://zscribe-uryls55n.livekit.cloud,LIVEKIT_API_KEY=APIwGAmCVQFir9w,LIVEKIT_API_SECRET=gvCrnJPpge1yzuoN36GDCI6WY4ymoGMzRVpPDgHZhjd,DEEPGRAM_API_KEY=61c3c0fd66e2d477c500122b310cebcdf1c5afd3,LANGFUSE_SECRET_KEY=sk-lf-9bccf64d-b093-4426-bb83-44f22c5ce017,LANGFUSE_PUBLIC_KEY=pk-lf-8d90388c-1772-4806-b918-9883a0692c2d,LANGFUSE_HOST=https://evals.zikrainfotech.com,API_BASE_URL=https://data-api-v2-292492747795.us-central1.run.app,DEFAULT_TEMPLATE_ID=bd9a2e9e-cdab-44d6-9882-58fc75ea9cda,DEFAULT_ORGANIZATION_ID=0da4a59a-275f-4f2d-92f0-5e0c60b0f1da,DEFAULT_PATIENT_ID=4b3a1edb-76c5-46f4-ad0f-3c164348202b,INTAKE_AGENT_NAME=ZScribe Intake Assistant,INTAKE_ORGANIZATION_NAME=ZScribe,HF_HUB_CACHE=/tmp/.cache/huggingface,TRANSFORMERS_CACHE=/tmp/.cache/transformers,PYTHONUNBUFFERED=1,BASETEN_API_KEY=eGdZ0Blx.o6nstCMXzdgM6RXE69ndCPaTCibXueQ0" \
  --cpu 2 \
  --memory 4Gi \
  --timeout 3600 \
  --concurrency 80 \
  --min-instances 1 \
  --max-instances 10 \
  --no-cpu-throttling \
  --project zscribe
```

**Deployment Time**: ~2-3 minutes
**Service URL**: https://intake-worker-v2-292492747795.us-central1.run.app

**Note**: This is the STABLE configuration using the original intake-worker-v2 image without EnglishModel.

---

## Environment Variables

### Complete Environment Variables List

| Variable | Value | Purpose |
|----------|-------|---------|
| `LIVEKIT_URL` | `wss://zscribe-uryls55n.livekit.cloud` | LiveKit server WebSocket URL |
| `LIVEKIT_API_KEY` | `APIwGAmCVQFir9w` | LiveKit API authentication |
| `LIVEKIT_API_SECRET` | `gvCrnJPpge1yzuoN36GDCI6WY4ymoGMzRVpPDgHZhjd` | LiveKit API secret |
| `SIP_OUTBOUND_TRUNK_ID` | `ST_Nxq7fztyRozT` | Telnyx SIP trunk identifier |
| `GOOGLE_API_KEY` | `AIzaSyC0KMSHyoApEo0_i7AsOiUFnw1tk8J-e4w` | Google AI services |
| `DEEPGRAM_API_KEY` | `61c3c0fd66e2d477c500122b310cebcdf1c5afd3` | Speech-to-text (Deepgram) |
| `CARTESIA_API_KEY` | `sk_car_tg3Q9p7R5n7EdejZGjuCKp` | Text-to-speech (Cartesia) |
| `SUPABASE_URL` | `https://nmefeljjgslggutiquqg.supabase.co` | Supabase project URL |
| `SUPABASE_KEY` | `eyJhbGci...` | Supabase service role key |
| `BASETEN_API_KEY` | `eGdZ0Blx.o6nstCMXzdgM6RXE69ndCPaTCibXueQ0` | Baseten ML inference |
| `LANGFUSE_SECRET_KEY` | `sk-lf-9bccf64d-b093-4426-bb83-44f22c5ce017` | Langfuse observability |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-8d90388c-1772-4806-b918-9883a0692c2d` | Langfuse public key |
| `LANGFUSE_HOST` | `https://evals.zikrainfotech.com` | Langfuse server URL |
| `API_BASE_URL` | `https://data-api-v2-292492747795.us-central1.run.app` | Backend API endpoint |
| `INTAKE_AGENT_NAME` | `intake-agent` | Agent identifier |
| `HF_HUB_CACHE` | `/tmp/.cache/huggingface` | Hugging Face model cache |
| `TRANSFORMERS_CACHE` | `/tmp/.cache/transformers` | Transformers model cache |

### Environment Variable Update Command

```bash
# Update specific environment variables
gcloud run services update intake-worker-v2 \
  --region us-central1 \
  --update-env-vars "API_BASE_URL=https://data-api-v2-292492747795.us-central1.run.app" \
  --project zscribe
```

---

## Critical Configuration

### 🔥 Must-Have Settings for Success

#### 1. **`--no-cpu-throttling`** (CRITICAL!)

**Why**: Without this flag, the worker fails to register with LiveKit properly.

```bash
--no-cpu-throttling
```

**Issue without it**: Worker starts but never shows "registered worker" in logs.
**Solution**: Always include `--no-cpu-throttling` flag.

#### 2. **Min Instances = 1**

**Why**: Keeps worker warm and ready to accept calls immediately.

```bash
--min-instances 1
```

**Trade-off**: Costs more (always-on instance) but eliminates cold start delays.

#### 3. **Memory = 4Gi**

**Why**: AI models (VAD, TTS, STT) require significant memory.

```bash
--memory 4Gi
```

**Issue with less**: Out-of-memory errors during calls.

#### 4. **Timeout = 3600 seconds**

**Why**: Calls can be long (up to 1 hour).

```bash
--timeout 3600
```

**Default**: 300 seconds (5 minutes) - too short for medical intake calls.

#### 5. **Model Caching Environment Variables**

**Why**: Models need writable cache directory in Cloud Run.

```bash
--set-env-vars "HF_HUB_CACHE=/tmp/.cache/huggingface,TRANSFORMERS_CACHE=/tmp/.cache/transformers"
```

**Issue without it**: Models fail to download at runtime.

---

## Troubleshooting

### Issue 1: Worker Not Registering

**Symptoms**:
- Logs show "Starting LiveKit worker..." but never "registered worker"
- Health check passes but no jobs accepted

**Solution**: Add `--no-cpu-throttling` flag

```bash
gcloud run services update intake-worker-v2 \
  --region us-central1 \
  --no-cpu-throttling \
  --project zscribe
```

---

### Issue 2: EnglishModel RuntimeError

**Symptoms**:
```
RuntimeError: livekit-plugins-turn-detector initialization failed.
Could not find file "model_q8.onnx"
```

**Solution**: Models must be downloaded during Docker build

Update `Dockerfile.worker`:
```dockerfile
RUN python src/download_models.py download-files || echo "Model download completed with warnings"
```

**Verify**: Check build logs for "Finished downloading files for livekit.plugins.turn_detector"

---

### Issue 3: Docker Push Authentication Failed

**Symptoms**:
```
ERROR: (gcloud.auth.docker-helper) Reauthentication failed
```

**Solution**: Re-authenticate with gcloud

```bash
gcloud auth login
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

### Issue 4: GitHub Secret Protection

**Symptoms**:
```
remote: - Push cannot contain secrets
remote:   - Telnyx API V2 Key
```

**Solution**: Never commit API keys to git. Use placeholders in documentation.

---

### Issue 5: Cold Start Too Slow

**Symptoms**:
- First call takes 20-30 seconds to connect
- Models downloading at runtime

**Solution**:
1. Pre-download models in Dockerfile ✅ (already done)
2. Set `--min-instances 1` to keep worker warm ✅ (already done)

---

## Deployment Checklist

### Pre-Deployment

- [ ] Code changes committed and pushed to GitHub
- [ ] Docker Desktop running
- [ ] `gcloud` authenticated (`gcloud auth login`)
- [ ] Docker registry authenticated (`gcloud auth configure-docker`)
- [ ] Environment variables reviewed and updated

### Build Phase

- [ ] Build Docker image with correct tag
- [ ] Verify build logs show model downloads completed
- [ ] Check image size is reasonable (~300 MB)
- [ ] Push image to Artifact Registry
- [ ] Verify image appears in GCP Console

### Deployment Phase

- [ ] Deploy with `--no-cpu-throttling` flag
- [ ] Set `--min-instances 1` for production
- [ ] Set `--memory 4Gi` minimum
- [ ] Set `--timeout 3600` for long calls
- [ ] Include all environment variables
- [ ] Verify deployment succeeds (no errors)

### Post-Deployment Verification

- [ ] Check Cloud Run logs for "registered worker"
- [ ] Verify no error messages in logs
- [ ] Test health endpoint: `curl https://intake-worker-v2-[...].run.app/health`
- [ ] Make test call to verify end-to-end functionality
- [ ] Check Langfuse for traces/logs
- [ ] Verify recording saved to Supabase

---

## Monitoring & Logs

### View Logs

```bash
# Stream logs in real-time
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=intake-worker-v2" --project zscribe

# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=intake-worker-v2" --limit 100 --format json --project zscribe

# Filter for errors only
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=intake-worker-v2 AND severity>=ERROR" --limit 50 --project zscribe
```

### Key Log Messages to Look For

✅ **Success Indicators**:
- `INFO:worker-server:Starting LiveKit worker...`
- `INFO:livekit.agents:registered worker` ← **CRITICAL**
- `INFO:livekit.agents:process initialized`
- `Default STARTUP TCP probe succeeded`

⚠️ **Warning Signs**:
- `RuntimeError: cannot simulate job, the worker is closed`
- `TimeoutError` during shutdown
- `CancelledError` (harmless cleanup warnings)

❌ **Critical Errors**:
- `ModuleNotFoundError`
- `Could not find file "model_q8.onnx"`
- `401 Unauthorized`
- `Connection refused`

---

## Service Management

### Update Service Configuration

```bash
# Update environment variables
gcloud run services update intake-worker-v2 \
  --region us-central1 \
  --update-env-vars "KEY=VALUE" \
  --project zscribe

# Update resources
gcloud run services update intake-worker-v2 \
  --region us-central1 \
  --memory 8Gi \
  --cpu 4 \
  --project zscribe

# Update scaling
gcloud run services update intake-worker-v2 \
  --region us-central1 \
  --min-instances 2 \
  --max-instances 20 \
  --project zscribe
```

### Scale to Zero (Pause Service)

```bash
gcloud run services update intake-worker-v2 \
  --region us-central1 \
  --min-instances 0 \
  --max-instances 0 \
  --project zscribe
```

### Resume Service

```bash
gcloud run services update intake-worker-v2 \
  --region us-central1 \
  --min-instances 1 \
  --max-instances 10 \
  --project zscribe
```

### Delete Service

```bash
gcloud run services delete intake-worker-v2 \
  --region us-central1 \
  --project zscribe
```

---

## Cost Optimization

### Current Configuration Cost Estimate

**intake-worker-v2** (Production):
- **CPU**: 2 vCPU
- **Memory**: 4Gi
- **Min Instances**: 1 (always-on)
- **Estimated Cost**: ~$50-80/month (always-on instance)

### Cost Reduction Options

1. **Use min-instances=0** (not recommended for production)
   - Saves ~$50/month
   - Adds 10-30 second cold start delay

2. **Reduce to 2Gi memory** (not recommended)
   - Saves ~$20/month
   - Risk of out-of-memory errors

3. **Use preemptible instances** (not available for Cloud Run)

**Recommendation**: Keep current configuration for production reliability.

---

## Version History

### intake-worker-v2 (Current - Dec 1, 2025)
- ✅ EnglishModel turn detection enabled
- ✅ BackgroundAudioPlayer for better audio
- ✅ Models pre-downloaded during build
- ✅ `--no-cpu-throttling` enabled
- ✅ API_BASE_URL: `https://data-api-v2-292492747795.us-central1.run.app`
- **Status**: Production-ready, successfully handling calls

### worker (Previous - Nov 28, 2025)
- ✅ Basic functionality working
- ❌ No EnglishModel (older version)
- ❌ Required `--no-cpu-throttling` discovery
- **Status**: Deprecated, use intake-worker-v2

### intake-worker-v3 (Attempted - Nov 28, 2025)
- ❌ Failed with multiprocessing errors
- ❌ AssertionError during cleanup
- **Status**: Abandoned

---

## Quick Reference

### Deploy New Version (Quick)

```bash
# 1. Build
docker build -f Dockerfile.worker -t us-central1-docker.pkg.dev/zscribe/intake-agent/intake-worker-v2:latest .

# 2. Push
docker push us-central1-docker.pkg.dev/zscribe/intake-agent/intake-worker-v2:latest

# 3. Deploy (copy full command from "Working Deployment Configuration" section above)
gcloud run deploy intake-worker-v2 --image us-central1-docker.pkg.dev/zscribe/intake-agent/intake-worker-v2:latest --region us-central1 --platform managed --allow-unauthenticated --cpu 2 --memory 4Gi --timeout 3600 --concurrency 80 --min-instances 1 --max-instances 10 --no-cpu-throttling --project zscribe --set-env-vars "LIVEKIT_URL=wss://zscribe-uryls55n.livekit.cloud,LIVEKIT_API_KEY=APIwGAmCVQFir9w,LIVEKIT_API_SECRET=gvCrnJPpge1yzuoN36GDCI6WY4ymoGMzRVpPDgHZhjd,SIP_OUTBOUND_TRUNK_ID=ST_Nxq7fztyRozT,GOOGLE_API_KEY=AIzaSyC0KMSHyoApEo0_i7AsOiUFnw1tk8J-e4w,DEEPGRAM_API_KEY=61c3c0fd66e2d477c500122b310cebcdf1c5afd3,CARTESIA_API_KEY=sk_car_tg3Q9p7R5n7EdejZGjuCKp,SUPABASE_URL=https://nmefeljjgslggutiquqg.supabase.co,SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5tZWZlbGpqZ3NsZ2d1dGlxdXFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODEwNzk2NywiZXhwIjoyMDczNjgzOTY3fQ.edGpV0Qb33smvYn80Sn93s6o-UlgZJ88QRUv3XNiEwQ,BASETEN_API_KEY=eGdZ0Blx.o6nstCMXzdgM6RXE69ndCPaTCibXueQ0,LANGFUSE_SECRET_KEY=sk-lf-9bccf64d-b093-4426-bb83-44f22c5ce017,LANGFUSE_PUBLIC_KEY=pk-lf-8d90388c-1772-4806-b918-9883a0692c2d,LANGFUSE_HOST=https://evals.zikrainfotech.com,API_BASE_URL=https://data-api-v2-292492747795.us-central1.run.app,INTAKE_AGENT_NAME=intake-agent,HF_HUB_CACHE=/tmp/.cache/huggingface,TRANSFORMERS_CACHE=/tmp/.cache/transformers"

# 4. Verify
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=intake-worker-v2" --limit 50 --project zscribe | grep "registered worker"
```

### Check Service Status

```bash
# Service info
gcloud run services describe intake-worker-v2 --region us-central1 --project zscribe

# Recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=intake-worker-v2" --limit 50 --project zscribe

# Check if worker registered
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=intake-worker-v2 AND textPayload=~'registered worker'" --limit 5 --project zscribe
```

---

## Support & Resources

### Documentation
- **LiveKit Agents**: https://docs.livekit.io/agents/
- **Cloud Run**: https://cloud.google.com/run/docs
- **Docker**: https://docs.docker.com/

### Internal Resources
- **Artifact Registry**: https://console.cloud.google.com/artifacts/docker/zscribe/us-central1/intake-agent
- **Cloud Run Console**: https://console.cloud.google.com/run?project=zscribe
- **Logs Explorer**: https://console.cloud.google.com/logs/query?project=zscribe

### Key Contacts
- **LiveKit Issues**: Check agent initialization and registration
- **Telnyx Issues**: Check SIP trunk and recording configuration
- **Supabase Issues**: Check database connectivity and storage

---

**Last Updated**: December 2, 2025
**Version**: 1.0
**Production Service**: `intake-worker-v2`
**Status**: ✅ Stable and Running
