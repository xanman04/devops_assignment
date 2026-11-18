FROM python:3.13.11-slim-bookworm@sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSLo /tmp/microsoft.deb https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i /tmp/microsoft.deb && rm /tmp/microsoft.deb \
    && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18=18.6.1.1-1 unixodbc \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app groups /app/groups
COPY --chown=app:app notifications /app/notifications
COPY --chown=app:app config /app/config
COPY --chown=app:app manage.py serve.py /app/
RUN mkdir /app/data && chown app:app /app/data
USER app
EXPOSE 8000
CMD ["python", "serve.py"]
