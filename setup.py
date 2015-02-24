from setuptools import setup

setup(
  name = 'lazyupdredis',
  packages = [ 'lazyupdredis' ],
  version = '1.0',
  description = 'Lazy Updates for Redis',
  author = 'K Saur',
  author_email = 'ksaur@umd.edu',
  url = 'https://github.com/plum-umd/schema_update',
  install_requires = [ 'redis',  'pyparsing' ],
  classifiers = []
)

