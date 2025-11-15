from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.relation import relation
from app.config import get

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
    return {
        "service": "sqs_uploader_service",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }

app.include_router(relation)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="localhost", port=8080, reload=True)