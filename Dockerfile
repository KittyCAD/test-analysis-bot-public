FROM python:3.13-bookworm

RUN pip install poetry

RUN poetry config virtualenvs.in-project true

RUN apt update && apt install -y libgraphviz-dev

WORKDIR /app

ENV VIRTUAL_ENV = .venv
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml poetry.lock ./
COPY . ./

RUN poetry install --with=deployment --without=docs --without=dev

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
