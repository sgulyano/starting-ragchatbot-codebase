# Course Materials RAG System

A Retrieval-Augmented Generation (RAG) system designed to answer questions about course materials using semantic search and AI-powered responses.

## Overview

This application is a full-stack web application that enables users to query course materials and receive intelligent, context-aware responses. It uses ChromaDB for vector storage, an Ollama Cloud model (default `gemma4:31b`) for AI generation, a local embedding model (`all-MiniLM-L6-v2`), and provides a web interface for interaction.


## Prerequisites

- Python 3.13 or higher
- uv (Python package manager)
- An Ollama API key (create one at ollama.com → Settings → API keys; the free plan works)
- **For Windows**: Use Git Bash to run the application commands - [Download Git for Windows](https://git-scm.com/downloads/win)

## Installation

1. **Install uv** (if not already installed)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install Python dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```bash
   OLLAMA_API_KEY=your_ollama_api_key_here
   # Optional: any tool-capable model from https://ollama.com/api/tags
   # OLLAMA_MODEL=gemma4:31b
   ```

## Running the Application

### Quick Start

Use the provided shell script:
```bash
chmod +x run.sh
./run.sh
```

### Manual Start

```bash
cd backend
uv run uvicorn app:app --reload --port 8000
```

The application will be available at:
- Web Interface: `http://localhost:8000`
- API Documentation: `http://localhost:8000/docs`

