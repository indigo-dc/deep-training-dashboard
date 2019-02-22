from flask import Flask
from flask_oidc import OpenIDConnect
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config.from_pyfile('config.cfg')

oidc = OpenIDConnect(app)

from app import routes

if __name__ == "__main__":
    app.run(host='0.0.0.0')

