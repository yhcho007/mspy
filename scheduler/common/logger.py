import logging, yaml
from pathlib import Path

conf = yaml.safe_load(open(Path(__file__).parent.parent/"conf.yml"))
log_conf = conf["logging"]

logging.basicConfig(
    filename=log_conf["path"],
    format=log_conf["format"],
    level=logging.INFO
)
logger = logging.getLogger(__name__)
