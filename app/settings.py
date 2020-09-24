import warnings

from app import app


toscaDir = app.config['TOSCA_TEMPLATES_DIR'] + "/"
toscaParamsDir = app.config.get('TOSCA_PARAMETERS_DIR')
common_toscas = app.config['COMMON_TOSCAS']
modules_yml = app.config['MODULES_YML']
iamUrl = app.config['IAM_BASE_URL']
github_secret = app.config['GITHUB_SECRET'].encode('utf-8')
if not github_secret:
    warnings.warn('Github secret is empty so reload requests to the Dashboard (to update Toscas and modules) are '
                  'not authenticated.')

orchestratorUrl = app.config['ORCHESTRATOR_URL']
orchestratorConf = {
  'cmdb_url': app.config.get('CMDB_URL'),
  'slam_url': app.config.get('SLAM_URL'),
  'im_url': app.config.get('IM_URL')
}

external_links = app.config.get('EXTERNAL_LINKS', [])
enable_advanced_menu = app.config.get('ENABLE_ADVANCED_MENU', "yes")
iamGroups = app.config.get('IAM_GROUP_MEMBERSHIP')
