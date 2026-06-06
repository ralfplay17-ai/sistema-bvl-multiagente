FROM langflowai/langflow:latest

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
