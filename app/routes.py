from app import app, oidc
from flask import json, current_app, render_template, request, redirect, url_for, flash, session
import requests, json
import yaml
import io, os, sys
from fnmatch import fnmatch


def to_pretty_json(value):
    return json.dumps(value, sort_keys=True,
                      indent=4, separators=(',', ': '))

app.jinja_env.filters['tojson_pretty'] = to_pretty_json

toscaDir=app.config.get('TOSCA_TEMPLATES_DIR') + "/"
toscaTemplates = []
for path, subdirs, files in os.walk(toscaDir):
   for name in files:
        if fnmatch(name, "*.yml") or fnmatch(name, "*.yaml"):
            # skip hidden files
            if name[0] != '.': 
               toscaTemplates.append( os.path.relpath(os.path.join(path, name), toscaDir ))

orchestratorUrl = app.config.get('ORCHESTRATOR_URL')

@app.route('/')
@app.route('/home')
@oidc.require_login
def home():
  if oidc.user_loggedin:
     info = oidc.user_getinfo(['preferred_username', 'email', 'sub'])
     app.logger.info("User logged-in: " + json.dumps(info))
     username = info.get('preferred_username')
     user_id = info.get('sub')
     session['username'] = username 
     
     if not oidc.credentials_store:
        oidc.logout()
        return redirect(url_for('home'))

     if user_id in oidc.credentials_store:
        try:
            access_token = oidc.get_access_token()
            headers = {'Authorization': 'bearer %s' % (access_token)}
            
            url = orchestratorUrl +  "/deployments"
            response = requests.get(url, headers=headers)

            if not response.ok:
               deployments = {}
               flash("Error retrieving deployment list: \n" + response.text)
            else:
               deployments = response.json()["content"]

            return render_template('deployments.html', deployments=deployments, username=username)

        except Exception,e: 
            flash("Error: " + e)
            return redirect(url_for('home'))


@app.route('/template/<depid>')
@oidc.require_login
def deptemplate(depid=None):
    access_token = oidc.get_access_token()
    headers = {'Authorization': 'bearer %s' % (access_token)}
    url = orchestratorUrl + "/deployments/" + depid + "/template"
    response = requests.get(url, headers=headers)

    if not response.ok:
      flash("Error getting template: " + response.text)
      return redirect(url_for('home'))

    template = response.text
    return render_template('deptemplate.html', template=template)

@app.route('/delete/<depid>')
@oidc.require_login
def depdel(depid=None):
    access_token = oidc.get_access_token()
    headers = {'Authorization': 'bearer %s' % (access_token)}
    url = orchestratorUrl + "/deployments/" + depid
    response = requests.delete(url, headers=headers)
    print response
    if response.status_code == 403:
       flash('You are not allowed to delete this deployment');
  
    return redirect(url_for('home'))

@app.route('/create', methods=['GET', 'POST'])
@oidc.require_login
def depcreate():
     access_token = oidc.get_access_token()

     if request.method == 'GET':
        return render_template('createdep.html', templates=toscaTemplates, inputs={})
     else:
        selected_tosca = request.form.get('tosca_template')
        
        with io.open( toscaDir + selected_tosca) as stream:
           template = yaml.load(stream)
           if 'topology_template' not in template:
             flash("Error reading template \"" + selected_tosca + "\": syntax is not correct. Please select another template.");
             return redirect(url_for('depcreate'))
           
           inputs = template['topology_template']['inputs']
           description = "N/A"
           if 'description' in template:
              description = template['description']
           return render_template('createdep.html', templates=toscaTemplates, selectedTemplate=selected_tosca, description=description,  inputs=inputs)
        
 
@app.route('/submit', methods=['POST'])
@oidc.require_login
def createdep():
     with io.open( toscaDir + request.args.get('template')) as stream:   
        payload = { "template" : stream.read(), "parameters": request.form.to_dict() }
      
     body= json.dumps(payload)
     
     access_token = oidc.get_access_token() 

     url = orchestratorUrl +  "/deployments/"
     headers = {'Content-Type': 'application/json', 'Authorization': 'bearer %s' % (access_token)}
     response = requests.post(url, data=body, headers=headers)

     if not response.ok:
               flash("Error submitting deployment: \n" + response.text)
    
     return redirect(url_for('home'))


