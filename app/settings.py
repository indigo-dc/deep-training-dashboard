from app import app

toscaDir = app.config['TOSCA_TEMPLATES_DIR'] + "/"
toscaParamsDir = app.config.get('TOSCA_PARAMETERS_DIR')
orchestratorUrl = app.config['ORCHESTRATOR_URL']
default_tosca = app.config['DEFAULT_TOSCA_NAME']

iamUrl = app.config['IAM_BASE_URL']


tempSlamUrl = app.config.get('SLAM_URL') if app.config.get('SLAM_URL') else "" 

orchestratorConf = {
  'cdb_url': app.config.get('CMDB_URL'),
  'slam_url': tempSlamUrl + "/rest/slam",
  'im_url': app.config.get('IM_URL')
}

external_links = app.config.get('EXTERNAL_LINKS') if app.config.get('EXTERNAL_LINKS') else []
