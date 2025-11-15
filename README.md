# SQS Uploader Service

A FastAPI-based microservice that uploads segment processing tasks to AWS SQS queue. This service provides RESTful API endpoints to create and track segment relationship jobs by sending messages to SQS for processing.

## 🌟 Features

- **FastAPI Web Server**: RESTful API with automatic documentation
- **SQS Uploader**: Sends messages to AWS SQS queue in batches
- **Database Integration**: PostgreSQL for job tracking, Neo4j for graph queries
- **Docker Ready**: Production-ready Dockerfile and docker-compose
- **Health Checks**: Built-in health monitoring endpoints
- **Auto-reload**: Development mode with hot reload

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         FastAPI Application             │
├─────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────┐  │
│  │   REST API  │  │   SQS Uploader  │  │
│  │  Endpoints  │  │   (Batch Send)  │  │
│  │             │  │                 │  │
│  └─────────────┘  └─────────────────┘  │
│         │                  │            │
└─────────┼──────────────────┼────────────┘
          │                  │
          ▼                  ▼
    ┌──────────┐      ┌──────────┐
    │PostgreSQL│      │ AWS SQS  │
    └──────────┘      └──────────┘
          ▲
          │
    ┌──────────┐
    │  Neo4j   │
    └──────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- AWS Account (for SQS)
- PostgreSQL database
- Neo4j database

### Option 1: Using Start Script (Recommended)

**Linux/Mac:**
```bash
chmod +x start.sh
./start.sh
```

**Windows PowerShell:**
```powershell
.\start.ps1
```

### Option 2: Using Make

```bash
# One-time setup
make setup

# Start services
make up

# View logs
make logs

# Stop services
make down
```

### Option 3: Manual Docker Compose

```bash
# Copy and configure environment
cp env.example .env
# Edit .env with your credentials

# Build and start
docker-compose up --build -d

# View logs
docker-compose logs -f web

# Stop
docker-compose down
```

## 📝 Configuration

### Environment Variables

Create a `.env` file from `env.example`:

```bash
cp env.example .env
```

Required variables:

```env
# Databases
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_PASSWORD=your-password
POSTGRES_URL=postgresql://user:pass@host:5432/db

# AWS SQS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
SQS_QUEUE_URL=https://sqs.region.amazonaws.com/account/queue
```

## 🔌 API Endpoints

Once running, access the API at `http://localhost:8080`

### Main Endpoints

- `GET /` - Service information and status
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation

### Relation Endpoints

- `POST /relation/{manifestation_id}` - Create a segment relation job and upload tasks to SQS
- `GET /relation/{job_id}/status` - Get job status
- `GET /relation/{manifestation_id}/all-relations` - Get all completed segment relations

## 📊 How It Works

1. **Create Job**: Client sends a POST request with manifestation_id
2. **Fetch Segments**: Service fetches all segments from Neo4j for the manifestation
3. **Create Database Records**: Creates job and task records in PostgreSQL
4. **Upload to SQS**: Sends messages to SQS in batches (max 10 per batch)
5. **Track Progress**: Clients can poll job status using the job_id

## 📊 Monitoring

### Check Service Status

```bash
# Using curl
curl http://localhost:8080/health

# Using Make
make health

# View logs
docker-compose logs -f web
```

### Health Check Response

```json
{
  "status": "healthy"
}
```

## 🛠️ Development

### Local Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### Hot Reload with Docker

The docker-compose setup includes volume mounts for hot reload:

```bash
docker-compose up
# Edit files in app/ directory
# Changes are automatically reflected
```

## 🚢 Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions for:

- **Cloud Platforms**: Render, Railway, AWS ECS, Google Cloud Run
- **Container Orchestration**: Kubernetes, Docker Swarm
- **CI/CD**: GitHub Actions, GitLab CI

### Quick Deploy Commands

**Build Production Image:**
```bash
docker build -t sqs-uploader-service:latest .
```

**Run Production Container:**
```bash
docker run -d \
  --name sqs-uploader \
  -p 8080:8080 \
  --env-file .env \
  sqs-uploader-service:latest
```

## 📁 Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI application
│   ├── relation.py          # API endpoints (SQS upload logic)
│   ├── config.py            # Configuration
│   ├── models.py            # Pydantic models
│   ├── neo4j_database.py    # Neo4j integration
│   └── db/
│       ├── postgres.py      # PostgreSQL setup
│       └── models.py        # SQLAlchemy models
├── Dockerfile               # Production Docker image
├── docker-compose.yml       # Multi-container setup
├── requirements.txt         # Python dependencies
├── start.sh                 # Quick start script (Linux/Mac)
├── start.ps1                # Quick start script (Windows)
├── Makefile                 # Make commands
├── DEPLOYMENT.md            # Deployment guide
└── env.example              # Environment template
```

## 🔧 Makefile Commands

```bash
make help      # Show all available commands
make build     # Build Docker images
make up        # Start services
make down      # Stop services
make logs      # View logs
make restart   # Restart services
make clean     # Remove containers and volumes
make shell     # Open shell in container
make health    # Check service health
make setup     # Full setup from scratch
```

## 🐛 Troubleshooting

### Common Issues

**1. SQS Upload Failed**
```bash
# Check logs for SQS errors
docker-compose logs web | grep "SQS"

# Verify AWS credentials
docker-compose exec web env | grep AWS
```

**2. Database Connection Failed**
```bash
# Test PostgreSQL connection
docker-compose exec web python -c "from app.db.postgres import engine; engine.connect()"

# Test Neo4j connection
docker-compose exec web python -c "from app.neo4j_database import Neo4JDatabase; Neo4JDatabase().verify_connectivity()"
```

**3. Port Already in Use**
```bash
# Change port in docker-compose.yml
ports:
  - "8081:8080"  # Use different external port
```

**4. Permission Denied (Linux)**
```bash
# Make scripts executable
chmod +x start.sh
```

### Debug Mode

Enable debug logging:

```env
LOG_LEVEL=DEBUG
```

## 🧪 Testing

```bash
# Run tests (when implemented)
make test

# Manual API testing
curl -X GET http://localhost:8080/health
curl -X POST http://localhost:8080/relation/{manifestation_id}
```

## 🔐 Security Notes

- Never commit `.env` file to version control
- Use IAM roles instead of access keys when deploying to AWS
- Rotate credentials regularly
- Use secrets management in production
- Keep dependencies updated

## 📚 Documentation

- [Deployment Guide](DEPLOYMENT.md) - Detailed deployment instructions
- [API Documentation](http://localhost:8080/docs) - Interactive API docs (when running)
- [FastAPI Docs](https://fastapi.tiangolo.com/) - FastAPI framework documentation
- [AWS SQS](https://docs.aws.amazon.com/sqs/) - AWS SQS documentation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

[Add your license here]

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review application logs
3. Open an issue on GitHub

---

**Made with ❤️ using FastAPI, Docker, and AWS SQS**
