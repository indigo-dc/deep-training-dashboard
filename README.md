<div align="center">
<img src="https://marketplace.deep-hybrid-datacloud.eu/images/logo-deep.png" alt="logo" width="300"/>
</div>

# DEEP-Hybrid-DataCloud training dashboard

> :warning: **Warning**: This is a fork from the [INDIGO PaaS Orchestrator - Simple Graphical UI ](https://github.com/indigo-dc/orchestrator-dashboard) that is being customized to accomodate ML/DL workloads over the DEEP services. This is still work in progress. A preliminary version is deployed [here](https://train.deep-hybrid-datacloud.eu/).

## Functionality

- IAM authentication
- Display user's deployments
- Display deployment details and template
- Delete deployment
- Create new deployment

The deep-training-dashboard is a Python application built with the [Flask](http://flask.pocoo.org/) microframework; [Flask-Dance](https://flask-dance.readthedocs.io/en/latest/) is used for Openid-Connect/OAuth2 integration.

The docker image uses [Gunicorn](https://gunicorn.org/) as WSGI HTTP server to serve the Flask Application.

## How to deploy the dashboard

1) Register a client in [DEEP-IAM](https://iam.deep-hybrid-datacloud.eu/) with the following properties:

    - redirect uri: `https://<DASHBOARD_HOST>:<PORT>/login/iam/authorized`.
    - scopes: `openid`, `email`, `profile`, `offline_access`.
    - introspection endpoint enabled.
    
2) Clone the tosca-templates repository to get a set of tosca templates that the dashboard will load, e.g.:

    ```git clone https://github.com/indigo-dc/tosca-templates```

3) Create a `config.json` file in `/app` (see the [example](app/config-sample.json)) an replace the values with your
 `IAM_CLIENT_ID`, `IAM_CLIENT_SECRET` and `TOSCA_TEMPLATES_DIR`. If you want that the reload requests (to update Tocas
 and modules list) from Github to be authenticated (so to ensure that they only come from your Github webhooks) you
 have to set `GITHUB_SECRET` to be the same as Github's webhook secret (see "[Keeping the Dashboard updated](#keeping-the-dashboard-updated)" below).

    ```json
    {
        "IAM_CLIENT_ID": "my_client_id",
        "IAM_CLIENT_SECRET": "my_client_secret",
        "IAM_BASE_URL": "https://iam.deep-hybrid-datacloud.eu",
    
        "ORCHESTRATOR_URL": "https://paas.cloud.cnaf.infn.it/orchestrator",
        "SLAM_URL": "https://paas.cloud.cnaf.infn.it:8443",
        "CMDB_URL": "http://paas.cloud.cnaf.infn.it/cmdb",
        "IM_URL": "https://paas.cloud.cnaf.infn.it/im",
        "MONITORING_URL": "https://deep-paas.cloud.ba.infn.it/monitoring-wrapper",

        "TOSCA_TEMPLATES_DIR": "../tosca-templates/deep-oc",
        "COMMON_TOSCAS": {
            "default": "deep-oc-marathon-webdav.yml",
            "minimal": "deep-oc-marathon-minimal.yml"
        },
        "MODULES_YML": "https://raw.githubusercontent.com/deephdc/deep-oc/master/MODULES.yml",
        "GITHUB_SECRET": "",
    
        "SUPPORT_EMAIL": "deep-support@listas.csic.es",
    
        "EXTERNAL_LINKS": [
            {
                "url": "https://marketplace.deep-hybrid-datacloud.eu",
                "menu_item_name": "DEEP Marketplace"
            },
            {
                "url": "https://docs.deep-hybrid-datacloud.eu",
                "menu_item_name": "Documentation"
            },
            {
                "url": "https://deep-hybrid-datacloud.eu",
                "menu_item_name": "DEEP-Hybrid-DataCloud project page"
            }
        ],
    
        "LOG_LEVEL": "info",
        "ENABLE_ADVANCED_MENU": "yes"
    }
    ```
    
4) Enable HTTPS

    You need to run the deep-training-dashboard on HTTPS (otherwise you will get an error); you can choose between
    - enabling the HTTPS support
    - using an HTTPS proxy
    
    Details are provided in the next paragraphs.

### Enabling HTTPS

You would need to provide
- a pair certificate/key that the container will read from the container paths `/certs/cert.pem` and `/certs/key.pem`;
- the environment variable `ENABLE_HTTPS` set to `True`


Run the docker container:
```bash
docker run -d -p 443:5001 --name='deep-training-dashboard' \
           -e ENABLE_HTTPS=True \
           -v $PWD/cert.pem:/certs/cert.pem \
           -v $PWD/key.pem:/certs/key.pem \
           -v $PWD/config.json:/app/app/config.json \
           -v $PWD/tosca-templates:/opt/tosca-templates \
           indigodatacloud/deep-training-dashboard:latest
```

Access the dashboard at `https://<DASHBOARD_HOST>/`

### Using an HTTPS Proxy

Example of configuration for nginx:

```
server {
      listen         80;
      server_name    YOUR_SERVER_NAME;
      return         301 https://$server_name$request_uri;
}

server {
    listen        443 ssl;
    server_name   YOUR_SERVER_NAME;
    access_log    /var/log/nginx/proxy-paas.access.log  combined;

    ssl on;
    ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
    ssl_certificate           /etc/nginx/cert.pem;
    ssl_certificate_key       /etc/nginx/key.pem;
    ssl_trusted_certificate   /etc/nginx/trusted_ca_cert.pem;

    location / {
        # Pass the request to Gunicorn
        proxy_pass http://127.0.0.1:5001/;

        proxy_set_header        X-Real-IP $remote_addr;
        proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header        X-Forwarded-Proto https;
        proxy_set_header        Host $http_host;
        proxy_redirect          http:// https://;
        proxy_buffering         off;
    }
}
```

Run the docker container:

```bash
docker run -d -p 5001:5001 --name='deep-training-dashboard' \
           -v $PWD/config.json:/app/app/config.json \
           -v $PWD/tosca-templates:/opt/tosca-templates \
           indigodatacloud/deep-training-dashboard:latest
```

> :warning: Remember to update the redirect uri in the IAM client to `https://<PROXY_HOST>/login/iam/authorized`

Access the dashboard at `https://<PROXY_HOST>/`

### Keeping the Dashboard updated

If you want the Dashboard to keep updated with the changes in the TOSCA repos or the modules list you will have 
to configure a [Github webhook](https://developer.github.com/webhooks/creating/) in those repos (for example [1] and [2])
so that any pushes in those repos trigger an update in the Dashboard.

The webhooks have to be configured as following:
* Payload URL: `<dashboard_url>/reload`
* Content type: `application/json`
* Secret: Has to be the same as `GITHUB_SECRET` in the config.
* Enable SSL is you are running over HTTPS and have valid certificates.
* Just the `push` events.
* Mark as Active.

Repo examples:
1. https://github.com/indigo-dc/tosca-templates
2. https://github.com/deephdc/deep-oc

### Performance tuning

You can change the number of gunicorn worker processes using the environment
variable `WORKERS`.  E.g. if you want to use 2 workers, launch the container
with the option `-e WORKERS=2` Check the
[documentation](http://docs.gunicorn.org/en/stable/design.html#how-many-workers)
for ideas on tuning this parameter.

## How to build and run the docker image

```bash
git clone https://github.com/indigo-dc/deep-training-dashboard.git
cd deep-training-dashboard
docker build -f docker/Dockerfile -t deep-training-dashboard .
```

To run the created image you have to export the `config.json` file (with your credentials) inside
the docker container:
```bash
docker run -d -p 5001:5001 -v $PWD/config.json:/app/app/config.json deep-training-dashboard
```

The dashboard will be accessible at http://0.0.0.0:5001 .
You can also choose to run image hosted on DockerHub:
```bash
docker run -d -p 5001:5001 -v $PWD/config.json:/app/app/config.json indigodatacloud/deep-training-dashboard
```

## How to setup a development environment

```bash
git clone https://github.com/indigo-dc/deep-training-dashboard.git
cd deep-training-dashboard
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

Start the dashboard app with Flask:
```bash
FLASK_app=orchdashboard flask run --host=0.0.0.0 --cert cert.pem --key privkey.pem --port 443
```

or with Gunicorn:
  
```bash
gunicorn --certfile=cert.pem --keyfile=key.pem --bind 0.0.0.0:443 orchdashboard:app --daemon
```    

## Troubleshooting

### SSL Cert Verification

If you see problems with the SLAM interaction, you would need to specify the
certificate to be used to verify the SSL connection. You can pass the path to
a `CA_BUNDLE` file or directory with certificates of trusted CAs setting the
parameter `SLAM_CERT` in the `config.json` file:

```json
{
  ...
  "SLAM_URL": "https://indigo-slam.cloud.ba.infn.it:8443",
  "SLAM_CERT": "/path/to/certfile"
}
```

If you are running the docker container, you need to ensure that the cert file
is available inside the container in the path set in the `SLAM_CERT` parameter,
i.e. you would use a bind mount (`-v $PWD/certfile:/path/to/cerfile`)

## References:

- https://2.python-requests.org/en/master/user/advanced/#ssl-cert-verification

