ARG BUILD_FROM=python:3.11-slim
FROM ${BUILD_FROM}

ENV LANG C.UTF-8
# Ensure tesseract can find language data
ENV TESSDATA_PREFIX=/usr/share/tessdata

# Install system dependencies needed for tesseract and opencv
# The Home Assistant base image can be Debian-based or Alpine-based, so detect and use the appropriate package manager
RUN if [ -f /etc/debian_version ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
      git \
      wget \
      curl \
      tesseract-ocr \
      libtesseract-dev \
      libleptonica-dev \
      pkg-config \
      build-essential \
      libgl1 \
      ca-certificates \
      python3 \
      python3-dev \
      python3-pip \
    && rm -rf /var/lib/apt/lists/*; \
  elif [ -f /etc/alpine-release ]; then \
    # Install common build tools and python/pip on Alpine. Package names for tesseract vary,
    # so try common names and verify the tesseract binary exists.
    apk add --no-cache git ca-certificates build-base pkgconf python3 py3-pip python3-dev wget curl || true; \
    apk add --no-cache tesseract-ocr || apk add --no-cache tesseract || true; \
    # Ensure python3 is available
    if ! command -v python3 >/dev/null 2>&1; then \
      echo "python3 not installed on Alpine" && exit 1; \
    fi; \
    # Verify tesseract binary is available
    if ! command -v tesseract >/dev/null 2>&1; then \
      echo "tesseract not installed on Alpine; tried tesseract-ocr and tesseract packages" && exit 1; \
    fi; \
  else \
    echo "Unsupported base image: please ensure tesseract, leptonica and build tools are installed" && exit 1; \
  fi

# Ensure tessdata directory exists and contains English traineddata
RUN mkdir -p /usr/share/tessdata && \
    if [ -f /usr/share/tessdata/eng.traineddata ]; then \
      echo "eng.traineddata already present"; \
    else \
      if command -v wget >/dev/null 2>&1; then \
        wget -q -O /usr/share/tessdata/eng.traineddata https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata; \
      elif command -v curl >/dev/null 2>&1; then \
        curl -fsSL -o /usr/share/tessdata/eng.traineddata https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata; \
      else \
        echo "wget/curl not available to download tessdata" && exit 1; \
      fi; \
    fi

# Copy run script and make executable
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Copy addon files
WORKDIR /app
COPY . /app

# Install Python packages used by the addon
RUN if [ -f /etc/debian_version ]; then \
    python3 -m pip install --no-cache-dir --break-system-packages --upgrade pip && \
    python3 -m pip install --no-cache-dir --break-system-packages \
      pytesseract \
      opencv-python-headless \
      numpy \
      imutils \
      paho-mqtt; \
  elif [ -f /etc/alpine-release ]; then \
    # On Alpine avoid building opencv-python from source (musl). Install numpy system package first,
    # run pip installs, then install py3-opencv afterward to avoid pip parsing opencv's package metadata
    # (which can contain non-standard version strings) during pip operations.
    apk add --no-cache py3-numpy || true; \
    # Install the remaining Python packages via pip (do NOT upgrade pip on Alpine).
    python3 -m pip install --no-cache-dir --break-system-packages \
      pytesseract \
      imutils \
      paho-mqtt; \
    # Now install the system OpenCV package after pip completes to provide cv2
    apk add --no-cache py3-opencv || true; \
  else \
    echo "Unsupported base image for Python package install" && exit 1; \
  fi

# Start the add-on by running the run script provided by the addon
CMD ["/run.sh"]

