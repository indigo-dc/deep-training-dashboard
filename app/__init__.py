from flask import Flask
from werkzeug.contrib.fixers import ProxyFix
from flask_dance.consumer import OAuth2ConsumerBlueprint
import logging

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)
app.secret_key="this.is.my.secretkey"
app.config.from_json('config.json')

iam_base_url=app.config['IAM_BASE_URL']
iam_token_url=iam_base_url + '/token'
iam_refresh_url=iam_base_url + '/token'
iam_authorization_url=iam_base_url + '/authorize'

iam_blueprint = OAuth2ConsumerBlueprint(
    "iam", __name__,
    client_id=app.config['IAM_CLIENT_ID'],
    client_secret=app.config['IAM_CLIENT_SECRET'],
    base_url=iam_base_url,
    token_url=iam_token_url,
    auto_refresh_url=iam_refresh_url,
    authorization_url=iam_authorization_url,
    redirect_to='home'
)
app.register_blueprint(iam_blueprint, url_prefix="/login")

from app import routes

if __name__ == "__main__":
    app.run(host='0.0.0.0')

