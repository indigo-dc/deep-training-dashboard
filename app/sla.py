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
    endpoint = data.get('endpoint')
    iam_enabled = data.get('iam_enabled')
    if iam_enabled == None:
        iam_enabled = "True"
    if ('properties' in data) and ('gpu_support' in data['properties']):
        service_type += " (gpu_support: {})".format(data['properties']['gpu_support'])

    return sitename, endpoint, service_type, iam_enabled


def is_enabling_services(deployment_type, service_type):

    if deployment_type == "":
        return True

    if deployment_type == "CLOUD":
        return True if service_type in [ "org.openstack.nova", "com.amazonaws.ec2" ] else False
    elif deployment_type == "MARATHON":
        return True if "eu.indigo-datacloud.marathon" in service_type else False
    elif deployment_type == "CHRONOS":
        return True if "eu.indigo-datacloud.chronos" in service_type else False
    elif deployment_type == "QCG":
        return True if service_type == "eu.deep.qcg" else False
    else:
        return True


def get_slas(access_token, slam_url, cmdb_url, deployment_type=""):

    headers = {'Authorization': 'bearer {}'.format(access_token)}
    url = slam_url + "/preferences/" + session['organisation_name']
    response = requests.get(url, headers=headers, timeout=20, verify=False)
    response.raise_for_status()
    slas = response.json()['sla']

    filtered_slas = []
    for i in range(len(slas)):
        sitename, endpoint, service_type, iam_enabled = get_sla_extra_info(access_token, slas[i]['services'][0]['service_id'], cmdb_url)

        if is_enabling_services(deployment_type, service_type):
            slas[i]['service_id'] = slas[i]['services'][0]['service_id']
            slas[i]['service_type'] = service_type
            slas[i]['sitename'] = sitename
            slas[i]['endpoint'] = endpoint
            slas[i]['iam_enabled'] = iam_enabled

            filtered_slas.append(slas[i])

    return filtered_slas
