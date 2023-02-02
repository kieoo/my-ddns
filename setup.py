#!/usr/bin/python
# coding=utf-8
"""
Created on 2023年01月28日
@author: qyke

"""

from setuptools import find_packages, setup

setup(
    name="my_ddns",
    version="1.1",
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    scripts=["ddns.py"],
    install_requires=["requests",
                      "alibabacloud_alidns20150109>=2.0.1, <3.0.0",
                      "alibabacloud_tea_util>=0.3.3, <1.0.0",
                      "alibabacloud_darabonba_env>=0.0.1, <1.0.0",
                      "alibabacloud_tea_openapi>=0.2.0, <1.0.0",
                      "alibabacloud_tea_console>=0.0.1, <1.0.0"]
)