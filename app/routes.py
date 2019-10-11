from app import app, iam_blueprint, sla as sla, settings, utils
from werkzeug.exceptions import Forbidden
from flask import json, render_template, request, redirect, url_for, flash, session, Markup
import requests, json
import yaml
import io, os, sys
from functools import wraps
from packaging import version

app.jinja_env.filters['tojson_pretty'] = utils.to_pretty_json

toscaTemplates = utils.loadToscaTemplates(settings.toscaDir)
toscaInfo = utils.extractToscaInfo(settings.toscaDir,settings.toscaParamsDir,toscaTemplates)

app.logger.debug("TOSCA INFO: " + json.dumps(toscaInfo))
app.logger.debug("EXTERNAL_LINKS: " + json.dumps(settings.external_links) )

@app.before_request
def before_request_checks():
    if 'external_links' not in session:
       session['external_links'] = settings.external_links

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
           return redirect(url_for('login'))

        if iam_blueprint.session.token['expires_in'] < 20:
            app.logger.debug("Force refresh token")
            iam_blueprint.session.get('/userinfo')

        validate_configuration()

        return f(*args, **kwargs)

    return decorated_function

@app.route('/settings')
@authorized_with_valid_token
def show_settings():
    return render_template('settings.html', iam_url=settings.iamUrl, orchestrator_url=settings.orchestratorUrl, orchestrator_conf=settings.orchestratorConf)

@app.route('/login')
def login():
    session.clear()
    return render_template('home.html')

@app.route('/slas')
@authorized_with_valid_token
def getslas():

  slas={}

  try:
    access_token = iam_blueprint.session.token['access_token']
    slas = sla.get_slas(access_token, settings.orchestratorConf['slam_url'], settings.orchestratorConf['cdb_url'])

  except Exception as e:
        flash("Error retrieving SLAs list: \n" + str(e), 'warning')

  return render_template('sla.html', slas=slas)


@app.route('/')
def home():
    if not iam_blueprint.session.authorized:
        return redirect(url_for('login'))
    
    account_info = iam_blueprint.session.get("/userinfo")

    if account_info.ok:
        account_info_json = account_info.json()

        if settings.iamGroups:
            user_groups = account_info_json['groups']
            if not set(settings.iamGroups).issubset(user_groups):
                app.logger.debug("No match on group membership. User group membership: " + json.dumps(user_groups))
                message = Markup('You need to be a member of the following IAM groups: {0}. <br> Please, visit <a href="{1}">{1}</a> and apply for the requested membership.'.format(json.dumps(settings.iamGroups), settings.iamUrl))
                raise Forbidden(description=message)
            
        session['username'] = account_info_json['name']
        session['gravatar'] = utils.avatar(account_info_json['email'], 26)
        session['organisation_name'] = account_info_json['organisation_name']
        access_token = iam_blueprint.token['access_token']

        return render_template('portfolio.html', templates=toscaInfo)


@app.route('/deployments')
@authorized_with_valid_token
def showdeployments():

    access_token = iam_blueprint.session.token['access_token']

    headers = {'Authorization': 'bearer %s' % (access_token)}

    url = settings.orchestratorUrl +  "/deployments?createdBy=me&page=0&size=9999"
    response = requests.get(url, headers=headers)

    deployments = {}
    if not response.ok:
        flash("Error retrieving deployment list: \n" + response.text, 'warning')
    else:
        deployments = response.json()["content"]
        app.logger.debug("Deployments: " + str(deployments))
    return render_template('deployments.html', deployments=deployments)



@app.route('/template/<depid>')
@authorized_with_valid_token
def deptemplate(depid=None):

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Authorization': 'bearer %s' % (access_token)}

    url = settings.orchestratorUrl + "/deployments/" + depid + "/template"
    response = requests.get(url, headers=headers)

    if not response.ok:
      flash("Error getting template: " + response.text)
      return redirect(url_for('home'))

    template = response.text
    return render_template('deptemplate.html', template=template)
#

@app.route('/log/<physicalId>')
@authorized_with_valid_token
def deplog(physicalId=None):

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Authorization': 'id = im; type = InfrastructureManager; token = %s;' % (access_token)}

    app.logger.debug("Configuration: " + json.dumps(settings.orchestratorConf))

    url = settings.orchestratorConf['im_url'] + "/infrastructures/" + physicalId + "/contmsg"
    response = requests.get(url, headers=headers, verify=False)

    if not response.ok:
      log="Not found"
    else:
      log = response.text
    return render_template('deplog.html', log=log)


@app.route('/delete/<depid>')
@authorized_with_valid_token
def depdel(depid=None):

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Authorization': 'bearer %s' % (access_token)}
    url = settings.orchestratorUrl + "/deployments/" + depid
    response = requests.delete(url, headers=headers)
       
    if not response.ok:
        flash("Error deleting deployment: " + response.text);
  
    return redirect(url_for('showdeployments'))


@app.route('/configure')
@authorized_with_valid_token
def configure():

    access_token = iam_blueprint.session.token['access_token']

    selected_tosca = request.args['selected_tosca']

    slas = sla.get_slas(access_token, settings.orchestratorConf['slam_url'], settings.orchestratorConf['cdb_url'])

    return render_template('createdep.html',
                           template=toscaInfo[selected_tosca],
                           selectedTemplate=selected_tosca,
                           slas=slas)


def add_sla_to_template(template, sla_id):
    # Add the placement policy

    if version.parse(utils.getOrchestratorVersion(settings.orchestratorUrl)) >= version.parse("2.2.0-SNAPSHOT"):
        toscaSlaPlacementType = "tosca.policies.indigo.SlaPlacement"
    else:
        toscaSlaPlacementType = "tosca.policies.Placement"

    template['topology_template']['policies'] = [
           {"deploy_on_specific_site": { "type": toscaSlaPlacementType, "properties": {"sla_id": sla_id}}}]

    app.logger.debug(yaml.dump(template, default_flow_style=False))

    return template
#        
# 
@app.route('/submit', methods=['POST'])
@authorized_with_valid_token
def createdep():

  access_token = iam_blueprint.session.token['access_token']

  app.logger.debug("Form data: " + json.dumps(request.form.to_dict()))

  with io.open( settings.toscaDir + request.args.get('template')) as stream:
      template = yaml.full_load(stream)

      form_data = request.form.to_dict()
     
      params={}
      if 'extra_opts.keepLastAttempt' in form_data:
         params['keepLastAttempt'] = 'true'
      else:
         params['keepLastAttempt'] = 'false'

      if form_data['extra_opts.schedtype'] == "man":
          template = add_sla_to_template(template, form_data['extra_opts.selectedSLA'])

      inputs = { k:v for (k,v) in form_data.items() if not k.startswith("extra_opts.") }

      app.logger.debug("Parameters: " + json.dumps(inputs))

      payload = { "template" : yaml.dump(template,default_flow_style=False, sort_keys=False), "parameters": inputs }


  url = settings.orchestratorUrl +  "/deployments/"
  headers = {'Content-Type': 'application/json', 'Authorization': 'bearer %s' % (access_token)}
  response = requests.post(url, json=payload, params=params, headers=headers)

  if not response.ok:
     flash("Error submitting deployment: \n" + response.text)

  return redirect(url_for('showdeployments'))
 


@app.route('/logout')
def logout():
   session.clear()
   iam_blueprint.session.get("/logout")
   return redirect(url_for('login'))
