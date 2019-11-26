import requests
from flask import session


def get_sla_extra_info(access_token, service_id, cmdb_url):
    headers = {'Authorization': 'bearer {}'.format(access_token)}
    url = cmdb_url + "/service/id/" + service_id
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    data = response.json()['data']
    service_type = data['service_type']
    sitename = data['sitename']
    if ('properties' in data) and ('gpu_support' in data['properties']):
        service_type += " (gpu_support: {})".format(data['properties']['gpu_support'])

    return sitename, service_type


def get_slas(access_token, slam_url, cmdb_url):

    headers = {'Authorization': 'bearer {}'.format(access_token)}
    url = slam_url + "/preferences/" + session['organisation_name']
    response = requests.get(url, headers=headers, timeout=20, verify=False)
    response.raise_for_status()
    slas = response.json()['sla']

    for i in range(len(slas)):
        sitename, service_type = get_sla_extra_info(access_token, slas[i]['services'][0]['service_id'], cmdb_url)
        slas[i]['service_type'] = service_type
        slas[i]['sitename'] = sitename

    return slas
