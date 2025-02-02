# FIXME: the following violations must be addressed gradually and unignored
# mypy: disable-error-code="no-untyped-call, no-untyped-def"

from urllib.parse import quote, urlencode, urljoin

from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    gettext_noop as _,
)

import requests as requests

from .plugin import CertFiles, CredentialPlugin, raise_for_status


aim_inputs = {
    'fields': [
        {
            'id': 'url',
            'label': _('CyberArk CCP URL'),
            'type': 'string',
            'format': 'url',
        },
        {
            'id': 'webservice_id',
            'label': _('Web Service ID'),
            'type': 'string',
            'help_text': _('The CCP Web Service ID. Leave blank to default to AIMWebService.'),
        },
        {
            'id': 'app_id',
            'label': _('Application ID'),
            'type': 'string',
            'secret': True,
        },
        {
            'id': 'client_key',
            'label': _('Client Key'),
            'type': 'string',
            'secret': True,
            'multiline': True,
        },
        {
            'id': 'client_cert',
            'label': _('Client Certificate'),
            'type': 'string',
            'secret': True,
            'multiline': True,
        },
        {
            'id': 'verify',
            'label': _('Verify SSL Certificates'),
            'type': 'boolean',
            'default': True,
        },
    ],
    'metadata': [
        {
            'id': 'object_query',
            'label': _('Object Query'),
            'type': 'string',
            'help_text': _('Lookup query for the object. Ex: Safe=TestSafe;Object=testAccountName123'),
        },
        {'id': 'object_query_format', 'label': _('Object Query Format'), 'type': 'string', 'default': 'Exact', 'choices': ['Exact', 'Regexp']},
        {
            'id': 'object_property',
            'label': _('Object Property'),
            'type': 'string',
            'help_text': _('The property of the object to return. Available properties: Username, Password and Address.'),
        },
        {
            'id': 'reason',
            'label': _('Reason'),
            'type': 'string',
            'help_text': _('Object request reason. This is only needed if it is required by the object\'s policy.'),
        },
    ],
    'required': ['url', 'app_id', 'object_query'],
}


def aim_backend(**kwargs):
    url = kwargs['url']
    client_cert = kwargs.get('client_cert', None)
    client_key = kwargs.get('client_key', None)
    verify = kwargs['verify']
    webservice_id = kwargs.get('webservice_id', '')
    app_id = kwargs['app_id']
    object_query = kwargs['object_query']
    object_query_format = kwargs['object_query_format']
    object_property = kwargs.get('object_property', '')
    reason = kwargs.get('reason', None)
    if webservice_id == '':
        webservice_id = 'AIMWebService'

    query_params = {
        'AppId': app_id,
        'Query': object_query,
        'QueryFormat': object_query_format,
    }
    if reason:
        query_params['reason'] = reason

    request_qs = '?' + urlencode(query_params, quote_via=quote)
    request_url = urljoin(url, '/'.join([webservice_id, 'api', 'Accounts']))

    with CertFiles(client_cert, client_key) as cert:
        res = requests.get(
            request_url + request_qs,
            timeout=30,
            cert=cert,
            verify=verify,
            allow_redirects=False,
        )
    sensitive_query_params = {
        'AppId': '****',
        'Query': '****',
        'QueryFormat': object_query_format,
    }
    if reason:
        sensitive_query_params['reason'] = '****'
    sensitive_request_qs = urlencode(
        sensitive_query_params,
        safe='*',
        quote_via=quote,
    )
    res.url = f'{request_url}?{sensitive_request_qs}'

    raise_for_status(res)
    # CCP returns the property name capitalized, username is camel case
    # so we need to handle that case
    if object_property == '':
        object_property = 'Content'
    elif object_property.lower() == 'username':
        object_property = 'UserName'
    elif object_property.lower() == 'password':
        object_property = 'Content'
    elif object_property.lower() == 'address':
        object_property = 'Address'
    elif object_property not in res:
        raise KeyError(
            f'Property {object_property} not found in object, available properties: Username, Password and Address',
        )
    else:
        object_property = object_property.capitalize()

    return res.json()[object_property]


aim_plugin = CredentialPlugin(
    'CyberArk Central Credential Provider Lookup',
    inputs=aim_inputs,
    backend=aim_backend,
)
