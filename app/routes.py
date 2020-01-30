import ast
import io
import os
import yaml
import json
from functools import wraps
from packaging import version
from copy import deepcopy

import requests
from werkzeug.exceptions import Forbidden
from flask import json, render_template, request, redirect, url_for, flash, session, Markup

from app import app, iam_blueprint, sla, settings, utils


app.jinja_env.filters['tojson_pretty'] = utils.to_pretty_json

toscaTemplates = utils.loadToscaTemplates(settings.toscaDir)
toscaInfo = utils.extractToscaInfo(toscaDir=settings.toscaDir,
                                   tosca_pars_dir=settings.toscaParamsDir,
                                   toscaTemplates=toscaTemplates,
                                   default_tosca=settings.default_tosca)

modules = utils.get_modules(tosca_templates=toscaTemplates,
                            default_tosca=settings.default_tosca,
                            tosca_dir=settings.toscaDir)
toscaTemplates = utils.loadToscaTemplates(settings.toscaDir)  # load again as we might have downloaded a new TOSCA during the get_modules

app.logger.debug("TOSCA INFO: {}".format(toscaInfo))
app.logger.debug("EXTERNAL_LINKS: {}".format(settings.external_links))
app.logger.debug("ENABLE_ADVANCED_MENU: {}".format(settings.enable_advanced_menu))


@app.before_request
def before_request_checks():
    session['external_links'] = settings.external_links
    session['enable_advanced_menu'] = settings.enable_advanced_menu


def validate_configuration():
    if not settings.orchestratorConf.get('im_url'):
        app.logger.debug("Trying to (re)load config from Orchestrator: " + json.dumps(settings.orchestratorConf))
        access_token = iam_blueprint.session.token['access_token']
        configuration = utils.getOrchestratorConfiguration(settings.orchestratorUrl, access_token)
        settings.orchestratorConf = configuration


def authorized_with_valid_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not iam_blueprint.session.authorized or 'username' not in session:
            account_info = iam_blueprint.session.get("/userinfo")
            if account_info.ok:
                account_info_json = account_info.json()

                if settings.iamGroups:
                    user_groups = account_info_json['groups']
                    if not set(settings.iamGroups).issubset(user_groups):
                        app.logger.debug(
                            "No match on group membership. User group membership: " + json.dumps(user_groups))
                        message = Markup('''
                        You need to be a member of the following IAM groups: {0}. <br>
                        Please, visit <a href="{1}">{1}</a> and apply for the requested membership.
                        '''.format(json.dumps(settings.iamGroups), settings.iamUrl))
                        raise Forbidden(description=message)

                session['username'] = account_info_json['name']
                session['gravatar'] = utils.avatar(account_info_json['email'], 26)
                session['organisation_name'] = account_info_json['organisation_name']
            else:
                return redirect(url_for('login', next=url_for(f.__name__, **kwargs), _external=True))

        elif iam_blueprint.session.token['expires_in'] < 20:
            app.logger.debug("Force refresh token")
            iam_blueprint.session.get('/userinfo')

        validate_configuration()

        return f(*args, **kwargs)

    return decorated_function


@app.route('/settings')
@authorized_with_valid_token
def show_settings():
    return render_template('settings.html',
                           iam_url=settings.iamUrl,
                           orchestrator_url=settings.orchestratorUrl,
                           orchestrator_conf=settings.orchestratorConf)


@app.route('/login')
def login():
    session.clear()
    session['next_url'] = request.args.get('next')
    return render_template('home.html')


@app.route('/slas')
@authorized_with_valid_token
def getslas():

    slas = {}
    try:
        access_token = iam_blueprint.session.token['access_token']
        slas = sla.get_slas(access_token, settings.orchestratorConf['slam_url'], settings.orchestratorConf['cmdb_url'])
    except Exception as e:
        flash("Error retrieving SLAs list: \n" + str(e), 'warning')

    return render_template('sla.html', slas=slas)


@app.route('/')
@authorized_with_valid_token
def home():
    if session.get('next_url'):
        next_url = session.get('next_url')
        session.pop('next_url', None)
        return redirect(next_url)

    return render_template('portfolio.html', templates=modules)


def get_deployments():

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Authorization': 'bearer {}'.format(access_token)}
    url = settings.orchestratorUrl + "/deployments?createdBy=me&page=0&size=9999"
    response = requests.get(url, headers=headers)

    deployments = {}
    if not response.ok:
        flash("Error retrieving deployment list: \n" + response.text, 'warning')
        return render_template('deployments.html', deployments=deployments)
    else:
        deployments = response.json()["content"]
        app.logger.debug("Deployments: " + str(deployments))
        return deployments


@app.route('/deployments')
@authorized_with_valid_token
def showdeployments():
    deployments= get_deployments()
    return render_template('deployments.html', deployments=deployments)


@app.route("/deployments/<uuid>")
@authorized_with_valid_token
def deployment_summary(uuid):
    deployments = get_deployments()
    deployment = next((d for d in deployments if d['uuid'] == uuid), None)
    if deployment is None:
        flash('This id matches no deployment')
        return redirect(url_for('showdeployments', _external=True))

    # Check if deployment has DEEPaaS V2
    deepaas_url = deployment['outputs']['deepaas_endpoint']
    try:
        versions = requests.get(deepaas_url).json()['versions']
        if 'v2' not in [v['id'] for v in versions]:
            raise Exception
    except Exception as e:
        flash('You need to be running DEEPaaS V2 to access to the training history')
        return redirect(url_for('showdeployments', _external=True))

    # Get info
    r = requests.get(deepaas_url + '/v2/models').json()
    training_info = {}
    for model in r['models']:
        r = requests.get('{}/v2/models/{}/train/'.format(deepaas_url, model['id']))
        training_info[model['id']] = r.json()

    return render_template('deployment_summary.html', deployment=deployment, training_info=training_info)


@app.route('/delete_training/<training_uuid>')
@authorized_with_valid_token
def delete_training(training_uuid):
    model = request.args.get('model')
    deployment = request.args.get('deployment')
    deployment = ast.literal_eval(deployment)
    requests.delete(deployment['outputs']['deepaas_endpoint'] + '/v2/models/{}/train/{}'.format(model, training_uuid))
    return redirect(url_for('deployment_summary', uuid=deployment['uuid'], _external=True))


@app.route('/template/<depid>')
@authorized_with_valid_token
def deptemplate(depid=None):

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Authorization': 'bearer {}'.format(access_token)}
    url = settings.orchestratorUrl + "/deployments/" + depid + "/template"
    response = requests.get(url, headers=headers)

    if not response.ok:
        flash("Error getting template: " + response.text)
        return redirect(url_for('home', _external=True))

    template = response.text
    return render_template('deptemplate.html', template=template)


@app.route('/log/<physicalId>')
@authorized_with_valid_token
def deplog(physicalId=None):

    app.logger.debug("Configuration: " + json.dumps(settings.orchestratorConf))

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Authorization': 'id = im; type = InfrastructureManager; token = {};'.format(access_token)}
    url = settings.orchestratorConf['im_url'] + "/infrastructures/" + physicalId + "/contmsg"
    response = requests.get(url, headers=headers, verify=False)

    if not response.ok:
        log = "Not found"
    else:
        log = response.text
    return render_template('deplog.html', log=log)


@app.route('/delete/<depid>')
@authorized_with_valid_token
def depdel(depid=None):

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Authorization': 'bearer {}'.format(access_token)}
    url = settings.orchestratorUrl + "/deployments/" + depid
    response = requests.delete(url, headers=headers)

    if not response.ok:
        flash("Error deleting deployment: " + response.text)

    return redirect(url_for('showdeployments', _external=True))


@app.route('/module/<selected_module>')
@authorized_with_valid_token
def configure(selected_module):

    # Parse form
    toscaname = request.args.get('toscaname', default='default')
    hardware = request.args.get('hardware', default='cpu')
    run = request.args.get('run', default='deepaas')

    # Update TOSCA conf
    selected_tosca = modules[selected_module]['toscas'][toscaname]
    tosca_info = toscaInfo[selected_tosca]
    try:
        if selected_tosca == settings.default_tosca:
            tosca_info = deepcopy(tosca_info)
            tosca_info['inputs']['docker_image']['default'] = modules[selected_module]['sources']['docker_registry_repo']
        tosca_info = utils.update_conf(conf=tosca_info, hardware=hardware, run=run)
    except Exception as e:
        print(e)
        flash("""Error updating the parameters according to the blue box selection. This tosca template might have some
        hardcoded options.""", 'warning')
    app.logger.debug("Template: " + json.dumps(tosca_info))
    form_conf = {'toscaname': {'selected': toscaname,
                               'available': list(modules[selected_module]['toscas'].keys())},
                 'hardware': {'selected': hardware,
                              'available': ['CPU', 'GPU']},
                 'run': {'selected': run,
                         'available': ['DEEPaaS', 'JupyterLab']}
                 }

    # Getting slas
    access_token = iam_blueprint.session.token['access_token']
    try:
        slas = sla.get_slas(access_token, settings.orchestratorConf['slam_url'], settings.orchestratorConf['cmdb_url'])
    except Exception as e:
        print(e)
        flash("Error retrieving the infrastructure provider's list. You probably won't be able to create "
              "your request correctly. Please report the problem to {}.".format(app.config.get('SUPPORT_EMAIL')),
              category='error')
        slas = None

    return render_template('createdep.html',
                           template=tosca_info,
                           selectedTemplate=selected_tosca,
                           selected_module=selected_module,
                           form_conf=form_conf,
                           slas=slas)


def add_sla_to_template(template, sla_id):
    # Add the placement policy

    if version.parse(utils.getOrchestratorVersion(settings.orchestratorUrl)) >= version.parse("2.2.0-SNAPSHOT"):
        toscaSlaPlacementType = "tosca.policies.indigo.SlaPlacement"
    else:
        toscaSlaPlacementType = "tosca.policies.Placement"

    template['topology_template']['policies'] = [
           {"deploy_on_specific_site": {"type": toscaSlaPlacementType, "properties": {"sla_id": sla_id}}}]

    app.logger.debug(yaml.dump(template, default_flow_style=False))

    return template


@app.route('/submit', methods=['POST'])
@authorized_with_valid_token
def createdep():

    app.logger.debug("Form data: " + json.dumps(request.form.to_dict()))

    template = request.args.get('template')
    with io.open(os.path.join(settings.toscaDir, template)) as stream:
        template = yaml.full_load(stream)

        form_data = request.form.to_dict()
        params = {}
        if 'extra_opts.keepLastAttempt' in form_data:
            params['keepLastAttempt'] = 'true'
        else:
            params['keepLastAttempt'] = 'false'

        if form_data['extra_opts.schedtype'] == "man":
            template = add_sla_to_template(template, form_data['extra_opts.selectedSLA'])

        inputs = {k: v for (k, v) in form_data.items() if not k.startswith("extra_opts.")}

        app.logger.debug("Parameters: " + json.dumps(inputs))

        payload = {"template": yaml.dump(template, default_flow_style=False, sort_keys=False),
                   "parameters": inputs}

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Content-Type': 'application/json', 'Authorization': 'bearer {}'.format(access_token)}
    url = settings.orchestratorUrl + "/deployments/"
    response = requests.post(url, json=payload, params=params, headers=headers)

    if not response.ok:
        flash("Error submitting deployment: \n" + response.text)

    return redirect(url_for('showdeployments', _external=True))


@app.route('/logout')
def logout():
    session.clear()
    iam_blueprint.session.get("/logout")
    return redirect(url_for('login', _external=True))
