django-graph-api-mail-backend
=============================

Simple [Django](https://www.djangoproject.com/) email backend to send emails
with [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/outlook-mail-concept-overview)


## Installation

1. Acquire `TENANT_ID`, `CLIENT_ID` and a `CLIENT_SECRET`
per [this guide](https://django-auth-adfs.readthedocs.io/en/latest/azure_ad_config_guide.html)

2. Install the backend from PyPI:

```bash
pip install django-graph-api-mail-backend
```

3. In your project's `settings.py` add the following configuration:

```python
ADFS_CLIENT_ID = '<client-id-from-azure>'
ADFS_CLIENT_SECRET = '<client-secret-from-azure>'
ADFS_TENANT_ID = '<tenant-id-from-azure>'

# tell django to use GraphAPI mail backend
EMAIL_BACKEND = "django_graph_api_mail_backend.graph_api_mail_backend.GraphAPIMailBackend"
```

## Example
The usual way of [sending emails with Django](https://docs.djangoproject.com/en/5.0/topics/email/) should work
flawlessly. For example:
```python
from django.core.mail import EmailMultiAlternatives

mail = EmailMultiAlternatives(
  subject='Some email subject',
  body="Email's body",
  from_email='me@my_organization.pl',
  to=['you@example.com'],
)
mail.attach_alternative(
    '<p>This is a simple HTML email body</p>',
    'text/html',
)
mail.send()
```

## Enabling logging 
The backend logs potential problems, such as emails without any recipients, and errors.

To see then, you need to enable the `django_graph_api_mail` logger in your `settings.py`:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django_graph_api_mail': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}
```

Please refer to the [offical Django documentation](https://docs.djangoproject.com/en/dev/topics/logging/)
to learnmore about logger configuration.

## Customizing requests timeout value
To change the value of the `timeout` argument passed to every `requests`
HTTP call set the `GRAPH_MAIL_BACKEND_TIMEOUT` in your `settings.py`:

```python
GRAPH_MAIL_BACKEND_TIMEOUT = 5 # seconds
```

## Legal Note
This repository is NOT officially supported or involved with [Microsoft](https://www.microsoft.com/en-us/) in any way.

The code is licensed under [BSD-3-Clause](https://opensource.org/license/BSD-3-clause).

