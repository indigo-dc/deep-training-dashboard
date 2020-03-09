from collections import OrderedDict
from hashlib import md5
import io
import json
from fnmatch import fnmatch
import os
import yaml

from flask import flash
import requests
import urllib.request

from app import settings


def to_pretty_json(value):
    return json.dumps(value, sort_keys=True,
                      indent=4, separators=(',', ': '))


def avatar(email, size):
    digest = md5(email.lower().encode('utf-8')).hexdigest()
    return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(digest, size)


def getOrchestratorVersion(orchestrator_url):
    url = orchestrator_url + "/info"
    response = requests.get(url)

    return response.json()['build']['version']


def getOrchestratorConfiguration(orchestrator_url, access_token):

    headers = {'Authorization': 'bearer {}'.format(access_token)}
    url = orchestrator_url + "/configuration"
    response = requests.get(url, headers=headers)

    configuration = {}
    if response.ok:
        configuration = response.json()

    return configuration


def loadToscaTemplates(directory):

    toscaTemplates = []
    for path, subdirs, files in os.walk(directory):
        for name in files:
            if fnmatch(name, "*.yml") or fnmatch(name, "*.yaml"):
                if name[0] != '.':  # skip hidden files
                    toscaTemplates.append(os.path.relpath(os.path.join(path, name), directory))

    return toscaTemplates


def extractToscaInfo(toscaDir, tosca_pars_dir, toscaTemplates, default_tosca):
    toscaInfo = {}
    for tosca in toscaTemplates:
        with io.open(toscaDir + tosca) as stream:
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
                    for k, v in template['metadata'].items():
                        toscaInfo[tosca]["metadata"][k] = v

                if 'inputs' in template['topology_template']:
                    toscaInfo[tosca]['inputs'] = template['topology_template']['inputs']

                # Add parameters code here
                if tosca_pars_dir:
                    tosca_pars_path = tosca_pars_dir + "/"  # this has to be reassigned here because is local.
                    for fpath, subs, fnames in os.walk(tosca_pars_path):
                        for fname in fnames:
                            if fnmatch(fname, os.path.splitext(tosca)[0] + '.parameters.yml') or \
                                    fnmatch(fname, os.path.splitext(tosca)[0] + '.parameters.yaml'):
                                if fname[0] != '.':  # skip hidden files
                                    tosca_pars_file = os.path.join(fpath, fname)
                                    with io.open(tosca_pars_file) as pars_file:
                                        toscaInfo[tosca]['enable_config_form'] = True
                                        pars_data = yaml.full_load(pars_file)
                                        toscaInfo[tosca]['inputs'] = pars_data["inputs"]
                                        if "tabs" in pars_data:
                                            toscaInfo[tosca]['tabs'] = pars_data["tabs"]

    return toscaInfo


def update_conf(conf, hardware='cpu', run='deepaas'):

    if run == 'deepaas':
        conf['inputs']['run_command']['default'] = 'deepaas-run --listen-ip=0.0.0.0'
        if hardware == 'gpu':
            conf['inputs']['run_command']['default'] += ' --listen-port=$PORT0'

    elif run == 'jupyterlab':
        flash('Remember to set a Jupyter password (mandatory).')
        conf['inputs']['run_command']['default'] = '/srv/.jupyter/run_jupyter.sh --allow-root'
        if hardware == 'gpu':
            conf['inputs']['run_command']['default'] = "jupyterPORT=$PORT2 " + conf['inputs']['run_command']['default']

    if hardware == 'cpu':
        conf['inputs']['num_cpus']['default'] = 1
        conf['inputs']['num_gpus']['default'] = 0
        conf['inputs']['docker_image']['default'] += ':cpu'
        conf['inputs']['run_command']['default'] = "monitorPORT=6006 " + conf['inputs']['run_command']['default']

    elif hardware == 'gpu':
        conf['inputs']['num_cpus']['default'] = 1
        conf['inputs']['num_gpus']['default'] = 1
        conf['inputs']['docker_image']['default'] += ':gpu'
        conf['inputs']['run_command']['default'] = "monitorPORT=$PORT1 " + conf['inputs']['run_command']['default']

    return conf


def get_modules(tosca_templates, default_tosca, tosca_dir):
    """
    We map modules available on the DEEP marketplace to available TOSCA files.
    If a module doesn't have a custom TOSCA, a default TOSCA will be loaded.
    """
    # Get the list of available modules in the Marketplace
    r = requests.get(settings.modules_yml)
    r.raise_for_status()
    yml_list = yaml.safe_load(r.content)
    if not yml_list:
        raise Exception('No modules found in {}'.format(settings.modules_yml))
    modules_list = [m['module'] for m in list(yml_list)]

    # Add the option for an external module
    modules_list.append('external')

    modules = OrderedDict()
    for module_url in modules_list:
        module_name = os.path.basename(module_url).lower().replace('_', '-')

        if module_name in modules.keys():
            raise Exception('Two modules are sharing the same name: {}'.format(module_name))

        # Get module description from metadata.json
        if module_name == 'external':
            metadata = {'title': 'Run your own module',
                        'summary': 'Use your own external container hosted in Dockerhub',
                        'tosca': [],
                        'sources': {'docker_registry_repo': ''}
                        }
        else:
            m_r = module_url.replace('https://github.com/', 'https://raw.githubusercontent.com/')
            metadata_url = '{}/master/metadata.json'.format(m_r)
            r = requests.get(metadata_url)
            metadata = r.json()

        # Find tosca names from metadata
        toscas = OrderedDict()
        for t in metadata['tosca']:
            try:
                tosca_name = os.path.basename(t['url'])
                if tosca_name == default_tosca:
                    continue
                if tosca_name not in tosca_templates:
                    urllib.request.urlretrieve(t['url'], os.path.join(tosca_dir, tosca_name))
                toscas[t['title'].lower()] = tosca_name
            except Exception as e:
                print('Error processing TOSCA in module {}'.format(module_name))

        # Add always default tosca
        toscas['default'] = default_tosca

        # Build the module dict
        modules[module_name] = {'toscas': toscas,
                                'url': module_url,
                                'title': metadata['title'],
                                'sources': metadata['sources'],
                                'description': metadata['summary'],
                                'metadata': {'icon': 'https://cdn4.iconfinder.com/data/icons/mosaicon-04/512/websettings-512.png',
                                             'display_name': metadata['title'],
                                             'tag': 'cpu, gpu'
                                             }
                                }

    return modules
