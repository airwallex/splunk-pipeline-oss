""" Org specific configuration  """

import yaml

with open('pipeline.yaml') as f:
    CONFIG = yaml.load(f, Loader=yaml.FullLoader)
