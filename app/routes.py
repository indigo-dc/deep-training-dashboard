from app import app, iam_blueprint, iam_base_url
from flask import json, current_app, render_template, request, redirect, url_for, flash, session
import requests, json
import yaml
import io, os, sys
from fnmatch import fnmatch
from hashlib import md5


def to_pretty_json(value):
    return json.dumps(value, sort_keys=True,
                      indent=4, separators=(',', ': '))

app.jinja_env.filters['tojson_pretty'] = to_pretty_json


def avatar(email, size):
  digest = md5(email.lower().encode('utf-8')).hexdigest()
  return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(digest, size)


toscaDir = app.config.get('TOSCA_TEMPLATES_DIR') + "/"
tosca_pars_dir = app.config.get('TOSCA_PARAMETERS_DIR')

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
       template = yaml.load(stream)

       toscaInfo[tosca] = {
                            "valid": True,
                            "description": "TOSCA Template",
                            "metadata": {
                                "icon": "https://cdn4.iconfinder.com/data/icons/mosaicon-04/512/websettings-512.png"
                            },
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
            enable_config_form = False
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
                                    enable_config_form = True
                                    pars_data = yaml.load(pars_file)
                                    toscaInfo[tosca]['inputs'] = pars_data["inputs"]
                                    if "tabs" in pars_data:
                                        toscaInfo[tosca]['tabs'] = pars_data["tabs"]


app.logger.debug("Extracted TOSCA INFO: " + json.dumps(toscaInfo))

orchestratorUrl = app.config.get('ORCHESTRATOR_URL')
slamUrl = app.config.get('SLAM_URL')
cmdbUrl = app.config.get('CMDB_URL')
slam_cert = app.config.get('SLAM_CERT')

@app.route('/settings')
def show_settings():
    if not iam_blueprint.session.authorized:
       return redirect(url_for('login'))
    return render_template('settings.html', orchestrator_url=orchestratorUrl, iam_url=iam_base_url)

@app.route('/login')
def login():
    session.clear()
    return render_template('home.html')


def get_sla_extra_info(access_token, service_id):
    headers = {'Authorization': 'bearer %s' % (access_token)}
    url = cmdbUrl + "/service/id/" + service_id
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    app.logger.info(json.dumps(response.json()['data']['service_type']))

    service_type=response.json()['data']['service_type']
    sitename=response.json()['data']['sitename'] 
    if 'properties' in response.json()['data']:
        if 'gpu_support' in response.json()['data']['properties']:
            service_type = service_type + " (gpu_support: " + str(response.json()['data']['properties']['gpu_support']) + ")"

    return sitename, service_type

def get_slas(access_token):

    headers = {'Authorization': 'bearer %s' % (access_token)}

    url = slamUrl + "/rest/slam/preferences/" + session['organisation_name']
    verify = True
    if slam_cert:
        verify = slam_cert
    response = requests.get(url, headers=headers, timeout=20, verify=verify)
    app.logger.info("SLA response status: " + str(response.status_code))

    response.raise_for_status()
    app.logger.info("SLA response: " + json.dumps(response.json()))
    slas = response.json()['sla']

    for i in range(len(slas)):
       sitename, service_type = get_sla_extra_info(access_token,slas[i]['services'][0]['service_id'])
       slas[i]['service_type']=service_type
       slas[i]['sitename']=sitename

    return slas

@app.route('/slas')
def getslas():

  if not iam_blueprint.session.authorized:
     return redirect(url_for('login'))

  slas={}

  try:
    access_token = iam_blueprint.token['access_token']
    slas = get_slas(access_token)

  except Exception as e:
        flash("Error retrieving SLAs list: \n" + str(e), 'warning')
        return redirect(url_for('home'))

  return render_template('sla.html', slas=slas)


@app.route('/')
def home():
    if not iam_blueprint.session.authorized:
        return redirect(url_for('login'))
    try:
        account_info = iam_blueprint.session.get("/userinfo")

        if account_info.ok:
            account_info_json = account_info.json()
            session['username'] = account_info_json['name']
            session['gravatar'] = avatar(account_info_json['email'], 26)
            session['organisation_name'] = account_info_json['organisation_name']
            access_token = iam_blueprint.token['access_token']

            return render_template('portfolio.html', templates=toscaInfo)

    except Exception as e:
        app.logger.error("Error: " + str(e))
        return redirect(url_for('logout'))

@app.route('/deployments')
def showdeployments():

  if not iam_blueprint.session.authorized:
     return redirect(url_for('login'))
  try:
    access_token = iam_blueprint.token['access_token']

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
  except Exception as e:
      app.logger.error("Error: " + str(e))
      return redirect(url_for('logout'))


@app.route('/template/<depid>')
def deptemplate(depid=None):

    if not iam_blueprint.session.authorized:
       return redirect(url_for('login'))

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
@app.route('/delete/<depid>')
def depdel(depid=None):

    if not iam_blueprint.session.authorized:
       return redirect(url_for('login'))

    access_token = iam_blueprint.session.token['access_token']
    headers = {'Authorization': 'bearer %s' % (access_token)}
    url = orchestratorUrl + "/deployments/" + depid
    response = requests.delete(url, headers=headers)
       
    if not response.ok:
        flash("Error deleting deployment: " + response.text);
  
    return redirect(url_for('showdeployments'))


@app.route('/configure')
def configure():
    if not iam_blueprint.session.authorized:
        return redirect(url_for('login'))

    access_token = iam_blueprint.session.token['access_token']



    selected_tosca = request.args['selected_tosca']

    try:
        slas = get_slas(access_token)

    except Exception as e:
        flash("Error retrieving SLAs list: \n" + str(e), 'warning')
        return redirect(url_for('home'))

    return render_template('createdep.html',
                           template=toscaInfo[selected_tosca],
                           selectedTemplate=selected_tosca,
                           slas=slas,
                           enable_config_form=enable_config_form)


def add_sla_to_template(template, sla_id):
    # Add the placement policy

    template['topology_template']['policies'] = [
        {"deploy_on_specific_site": {"type": "tosca.policies.Placement", "properties": {"sla_id": sla_id}}}]
    app.logger.info(yaml.dump(template, default_flow_style=False))

    return template
#        
# 
@app.route('/submit', methods=['POST'])
def createdep():

  if not iam_blueprint.session.authorized:
     return redirect(url_for('login'))

  access_token = iam_blueprint.session.token['access_token']

  app.logger.debug("Form data: " + json.dumps(request.form.to_dict()))

  try:
     with io.open( toscaDir + request.args.get('template')) as stream:
         template = yaml.load(stream)

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
 
  except Exception as e:
     flash("Error submitting deployment:" + str(e) + ". Please retry")
     return redirect(url_for('home'))


@app.route('/logout')
def logout():
   session.clear()
   iam_blueprint.session.get("/logout")
#   del iam_blueprint.session.token
   return redirect(url_for('login'))
