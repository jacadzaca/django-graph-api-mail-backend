#!/usr/bin/env python3
from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

setup(
    name='django-graph-api-mail-backend',
    version='1.0.0',
    description='Django email backend to send emails with Microsoft Graph API',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='jacadzaca',
    author_email='vitouejj@gmail.com',
    url='https://github.com/jacadzaca/django_graph_api_mail_backend',
    install_requires=[
        'requests',
        'Django',
    ],
    license='BSD-3-Clause',
    packages=find_packages(
        exclude=(
            'tests',
            'venv',
        ),
    ),
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
)
