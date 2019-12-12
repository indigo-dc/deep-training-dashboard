from app import app


toscaDir = app.config['TOSCA_TEMPLATES_DIR'] + "/"
toscaParamsDir = app.config.get('TOSCA_PARAMETERS_DIR')
default_tosca = app.config['DEFAULT_TOSCA_NAME']
modules_yml = app.config['MODULES_YML']
iamUrl = app.config['IAM_BASE_URL']

orchestratorUrl = app.config['ORCHESTRATOR_URL']
orchestratorConf = {
  'cmdb_url': app.config.get('CMDB_URL'),
  'slam_url': app.config.get('SLAM_URL') + "/rest/slam",
  'im_url': app.config.get('IM_URL')
}

external_links = app.config.get('EXTERNAL_LINKS', [])
enable_advanced_menu = app.config.get('ENABLE_ADVANCED_MENU', "yes")
iamGroups = app.config.get('IAM_GROUP_MEMBERSHIP')
