# MoroTracker is a single zero-dependency Python process (server.py) that serves
# both the static single-page app (index.html) and its JSON state API (/state).
# No build step, no package manager — just copy the two files onto a slim Python
# base. Caddy fronts this container on the shared proxy network (moro:8787).
FROM python:3.12-alpine

WORKDIR /app
COPY sync-backend/server.py /app/server.py
COPY index.html /app/index.html

# State persists on an external volume mounted at /app/data (see compose).
# No TZ: the server does no date math — streak/day logic is all client-side.
ENV MORO_DATA=/app/data/moro-state.json \
    MORO_STATIC=/app/index.html \
    MORO_PORT=8787
VOLUME ["/app/data"]
EXPOSE 8787

CMD ["python3", "/app/server.py"]
