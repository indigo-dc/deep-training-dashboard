FROM python:3.7

COPY . /app
WORKDIR /app/

ENV PYTHONPATH=/app

RUN pip install gunicorn && pip install -r /app/requirements.txt

EXPOSE 5001

ENV TIMEOUT 60
ENV ENABLE_HTTPS False

COPY ./docker/start.sh /start.sh

CMD ["/bin/bash","/start.sh"]



