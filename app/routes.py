from app import app, iam_blueprint, iam_base_url, sla as sla
from flask import json, current_app, render_template, request, redirect, url_for, flash, session
import requests, json
import yaml
import io, os, sys
from fnmatch import fnmatch
from hashlib import md5
from functools import wraps


def to_pretty_json(value):
    return json.dumps(value, sort_keys=True,
                      indent=4, separators=(',', ': '))

app.jinja_env.filters['tojson_pretty'] = to_pretty_json


def avatar(email, size):
  digest = md5(email.lower().encode('utf-8')).hexdigest()
  return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(digest, size)


toscaDir = app.config.get('TOSCA_TEMPLATES_DIR') + "/"
tosca_pars_dir = app.config.get('TOSCA_PARAMETERS_DIR')
orchestratorUrl = app.config.get('ORCHESTRATOR_URL')
imUrl = app.config.get('IM_URL')

toscaTemplates = []
for path, subdirs, files in os.walk(toscaDir):
   for name in files:
        if fnmatch(name, "*.yml") or fnmatch(name, "*.yaml"):
            # skip hidden files
            if name[0] != '.': 
               toscaTemplates.append( os.path.relpath(os.path.join(path, name), toscaDir ))

#toscaTemplates.sort(key=str.lower)
toscaInfo = {}
for tosca in toscaTemplates:
    with io.open( toscaDir + tosca) as stream:
       template = yaml.full_load(stream)

       toscaInfo[tosca] = {
                            "valid": True,
                            "description": "TOSCA Template",
                            "metadata": {
                                "icon": "https://cdn4.iconfinder.com/data/icons/mosaicon-04/512/websettings-512.png"
                            },
                            "enable_config_form": False,
                            "inputs": {},
                            "tabs": {}
                          }

       if 'topology_template' not in template:
           toscaInfo[tosca]["valid"] = False

       else:

            if 'description' in template:
                toscaInfo[tosca]["description"] = template['description']

            if 'metadata' in template and template['metadata'] is not None:
               for k,v in template['metadata'].items():
                   toscaInfo[tosca]["metadata"][k] = v

               if 'icon' not in template['metadata']:
                   toscaInfo[tosca]["metadata"]['icon'] = "xxxx"

            if 'inputs' in template['topology_template']:
               toscaInfo[tosca]['inputs'] = template['topology_template']['inputs']

            ## add parameters code here
            tabs = {}
            if tosca_pars_dir:
                tosca_pars_path = tosca_pars_dir + "/"  # this has to be reassigned here because is local.
                for fpath, subs, fnames in os.walk(tosca_pars_path):
                    for fname in fnames:
                        if fnmatch(fname, os.path.splitext(tosca)[0] + '.parameters.yml') or \
                                fnmatch(fname, os.path.splitext(tosca)[0] + '.parameters.yaml'):
                            # skip hidden files
                            if fname[0] != '.':
                                tosca_pars_file = os.path.join(fpath, fname)
                                with io.open(tosca_pars_file) as pars_file:
                                    toscaInfo[tosca]['enable_config_form'] = True
                                    pars_data = yaml.full_load(pars_file)
                                    toscaInfo[tosca]['inputs'] = pars_data["inputs"]
                                    if "tabs" in pars_data:
                                        toscaInfo[tosca]['tabs'] = pars_data["tabs"]


app.logger.debug("Extracted TOSCA INFO: " + json.dumps(toscaInfo))


def authorized_with_valid_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):


        if not iam_blueprint.session.authorized or 'username' not in session:
           return redirect(url_for('login'))

        if iam_blueprint.session.token['expires_in'] < 20:
            app.logger.debug("Force refresh token")
            iam_blueprint.session.get('/userinfo')

        return f(*args, **kwargs)

    return decorated_function

@app.route('/settings')
@authorized_with_valid_token
def show_settings():
    return render_template('settings.html', orchestrator_url=orchestratorUrl, iam_url=iam_base_url)

@app.route('/login')
def login():
    session.clear()
    return render_template('home.html')

@app.route('/slas')
@authorized_with_valid_token
def getslas():

  slas={}

  try:
    access_token = iam_blueprint.token['access_token']
    slas = sla.get_slas(access_token)

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
        session['username'] = account_info_json['name']
        session['gravatar'] = avatar(account_info_json['email'], 26)
        session['organisation_name'] = account_info_json['organisation_name']
        access_token = iam_blueprint.token['access_token']

        return render_template('portfolio.html', templates=toscaInfo)


@app.route('/deployments')
@authorized_with_valid_token
def showdeployments():

    access_token = iam_blueprint.session.token['access_token']

    headers = {'Authorization': 'bearer %s' % (access_token)}

    url = orchestratorUrl +  "/deployments?createdBy=me&page=0&size=9999"
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

    url = orchestratorUrl + "/deployments/" + depid + "/template"
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

    url = imUrl + "/infrastructures/" + physicalId + "/contmsg"
    response = requests.get(url, headers=headers)

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
    url = orchestratorUrl + "/deployments/" + depid
    response = requests.delete(url, headers=headers)
       
    if not response.ok:
        flash("Error deleting deployment: " + response.text);
  
    return redirect(url_for('showdeployments'))


@app.route('/configure')
@authorized_with_valid_token
def configure():

    access_token = iam_blueprint.session.token['access_token']

    selected_tosca = request.args['selected_tosca']

    slas = sla.get_slas(access_token)

    return render_template('createdep.html',
                           template=toscaInfo[selected_tosca],
                           selectedTemplate=selected_tosca,
                           slas=slas)


def add_sla_to_template(template, sla_id):
    # Add the placement policy

    template['topology_template']['policies'] = [
        {"deploy_on_specific_site": {"type": "tosca.policies.Placement", "properties": {"sla_id": sla_id}}}]
    app.logger.debug(yaml.dump(template, default_flow_style=False))

    return template
#        
# 
@app.route('/submit', methods=['POST'])
@authorized_with_valid_token
def createdep():

  access_token = iam_blueprint.session.token['access_token']

  app.logger.debug("Form data: " + json.dumps(request.form.to_dict()))

  with io.open( toscaDir + request.args.get('template')) as stream:
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


  url = orchestratorUrl +  "/deployments/"
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
