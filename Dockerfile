FROM langflowai/langflow:latest

# Fix: SQLAlchemy UUID type handler crashes when folder_id is a string instead of UUID object
RUN sed -i 's/value = value\.hex$/value = value.hex if not isinstance(value, str) else value.replace("-", "")/' \
    /app/.venv/lib/python3.14/site-packages/sqlalchemy/sql/sqltypes.py && \
    find /app/.venv/lib/python3.14/site-packages/sqlalchemy/sql/__pycache__ -name 'sqltypes*.pyc' -delete

RUN pip install --no-cache-dir \
    pyswarms==1.3.0 \
    newsapi-python==0.2.7 \
    pandas \
    numpy \
    scipy \
    requests \
    yfinance \
    feedparser

RUN mkdir -p /app/flows /app/data_bvl/data

COPY sistema_bvl.json /app/flows/sistema_bvl.json
COPY data_bvl/ /app/data_bvl/
COPY start.sh /app/start.sh
USER root
RUN chmod +x /app/start.sh

WORKDIR /app

ENV LANGFLOW_LOAD_FLOWS_PATH=/app/flows

EXPOSE 7860

CMD ["/app/start.sh"]
