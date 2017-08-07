#!/usr/bin/env python3
# -*-coding:utf-8-*-

"""
编写最新的配置文件
"""
from www import config_default

# create a override
def merge(defaults,override):
    r ={}
    for name,value in defaults.items():
        if name in override:
            if isinstance((value,dict)):
                r[name] = merge(value,override[name])
            else:
                r[name] = override[name]
        else:
            r[name] = defaults[name]
    return r

config = config_default

try:
    from www import config_override:
    merge(config,config_override.configs)
    print(merge(config,config_override.configs))
except ImportError:
    pss


