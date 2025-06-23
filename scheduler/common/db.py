import oracledb
import yaml

with open("conf.yml") as f:
    config = yaml.safe_load(f)

def get_connection():
    db_conf = config['db']
    return oracledb.connect(user=db_conf['user'], password=db_conf['password'], dsn=db_conf['dsn'])