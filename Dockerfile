FROM python:3.12-slim

ARG BGUTIL_VERSION=2.0.0

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    unzip \
    curl \
    git \
    ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://deno.land/install.sh | sh

ENV DENO_INSTALL="/root/.deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"
ENV YOUTUBE_POT_ENABLED="true"
ENV YOUTUBE_POT_PROVIDER_URL="http://127.0.0.1:4416"
ENV YOUTUBE_PLAYER_CLIENTS="mweb,web_safari,tv,web"
ENV YOUTUBE_AUTO_UPDATE_TOOLS="true"
ENV YOUTUBE_COOKIES_FILE="cookies/cookies.txt"

# Native HTTP PO-token provider. It stays bound to localhost and is started
# by ./start alongside the music bot.
RUN git clone --depth 1 --branch "${BGUTIL_VERSION}" \
    https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git \
    /opt/bgutil-ytdlp-pot-provider && \
    cd /opt/bgutil-ytdlp-pot-provider/server && \
    deno install --allow-scripts=npm:canvas --frozen

WORKDIR /app

COPY requirements.txt ./

RUN python3.12 -m pip install --upgrade pip && \
    python3.12 -m pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY . .

RUN python3.12 -m compileall -q AlexaMusic config strings genstring.py

CMD ["bash", "start"]
