FROM python:3.10-slim

# --------------------------------------------------
# System dependencies
# --------------------------------------------------
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    cmake \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --------------------------------------------------
# Performance: FORCE AVX2 for llama.cpp (CRITICAL)
# --------------------------------------------------
ENV CMAKE_ARGS="-DLLAMA_AVX2=ON"
ENV FORCE_CMAKE=1

# --------------------------------------------------
# Copy package metadata + source (ORDER MATTERS)
# --------------------------------------------------
COPY pyproject.toml README.md LICENSE ./
COPY axiom_sql_reflex/ ./axiom_sql_reflex/

# --------------------------------------------------
# Install Python dependencies + package
# --------------------------------------------------
RUN pip install --upgrade pip \
    && pip install .

# --------------------------------------------------
# Runtime directories (mounted by compose)
# --------------------------------------------------
RUN mkdir -p /app/data /app/models

# --------------------------------------------------
# Health / sanity check
# --------------------------------------------------
CMD ["python", "-c", "import axiom_sql_reflex; print('Axiom SQL-Reflex v4 container ready')"]
