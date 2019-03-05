#!/bin/bash



if [ "${ENABLE_HTTPS}" == "True" ]; then
  if test -e /certs/cert.pem && test -f /certs/key.pem ; then
    exec gunicorn --bind 0.0.0.0:5001 --certfile /certs/cert.pem --keyfile /certs/key.pem --timeout "$TIMEOUT"  orchdashboard:app
  else
    echo "[ERROR] File /certs/cert.pem or /certs/key.pem NOT FOUND!"
    exit 1
  fi
else
  exec gunicorn --bind 0.0.0.0:5001 --timeout "$TIMEOUT"  orchdashboard:app
fi
