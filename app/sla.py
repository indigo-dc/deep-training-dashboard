import requests, json
from flask import session
from app import app

slam_cert = app.config.get('SLAM_CERT')
slamUrl = app.config.get('SLAM_URL')
cmdbUrl = app.config.get('CMDB_URL')

def get_sla_extra_info(access_token, service_id):
    headers = {'Authorization': 'bearer %s' % (access_token)}
    url = cmdbUrl + "/service/id/" + service_id
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    service_type=response.json()['data']['service_type']
    sitename=response.json()['data']['sitename']
    if 'properties' in response.json()['data']:
        if 'gpu_support' in response.json()['data']['properties']:
            service_type = service_type + " (gpu_support: " + str(response.json()['data']['properties']['gpu_support']) + ")"

    return sitename, service_type

def get_slas(access_token):

    headers = {'Authorization': 'bearer %s' % (access_token)}

    app.logger.debug(slamUrl)

    url = slamUrl + "/rest/slam/preferences/" + session['organisation_name']
    verify = True
    if slam_cert:
        verify = slam_cert
    response = requests.get(url, headers=headers, timeout=20, verify=verify)
    app.logger.debug("SLA response status: " + str(response.status_code))

    response.raise_for_status()
    app.logger.debug("SLA response: " + json.dumps(response.json()))
    slas = response.json()['sla']

    for i in range(len(slas)):
       sitename, service_type = get_sla_extra_info(access_token,slas[i]['services'][0]['service_id'])
       slas[i]['service_type']=service_type
       slas[i]['sitename']=sitename

    return slas
