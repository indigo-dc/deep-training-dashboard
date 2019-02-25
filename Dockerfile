FROM python:3.7

RUN pip install gunicorn

COPY . /app
WORKDIR /app/

ENV PYTHONPATH=/app

RUN pip install -r /app/requirements.txt

EXPOSE 5001

ENV TIMEOUT 60
CMD gunicorn --bind 0.0.0.0:5001 --timeout "$TIMEOUT"  orchdashboard:app


