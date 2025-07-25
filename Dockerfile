FROM python:3.13.5-bookworm

RUN pip install poetry
RUN poetry config virtualenvs.in-project true
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml poetry.lock ./
COPY . ./

RUN poetry install --only=main
RUN ./manage.py collectstatic --no-input

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
