# -*- coding: utf-8 -*-

_author = 'Mike Burr'
_email = 'mburr@unintuitive.com'
__author__ = '% <%>' % (_author, _email)

from distutils.core import setup
import time

# my modules
import dunaway

# README.rst dynamically generated:
with open('README', 'w') as f:
    f.write(dunaway.__doc__)

NAME = dunaway.__name__

def read(file):
    with open(file, 'r') as f:
        return f.read().strip()

setup(
    name=NAME,
    version='0.0.1-%s' % time.time(),
    long_description=read('README'),
    author=_author,
    author_email=_email,
    provides=[NAME],
    requires=['flask', 'request'],
    packages=[NAME],
    keywords=[],
    package_data={'dunaway': ['resources/*']},
    scripts=[
        'bin/dunaway-print-dnsmasq-conf',
        'bin/dunaway-www-server',
    ],
)
