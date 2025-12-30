"""
Importing necessary libraries for fastapi application
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.job.job_views import job_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="sqs_uploader_service",
    description="SQS uploader service for OpenPecha segment processing",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "sqs_uploader_service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    """Server Health Check Status"""
    return {
        "status": "healthy"
    }


app.include_router(job_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="localhost", port=8080, reload=True)

