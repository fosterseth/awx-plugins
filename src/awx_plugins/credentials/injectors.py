# FIXME: the following violations must be addressed gradually and unignored
# mypy: disable-error-code="no-untyped-call, no-untyped-def"

import json
import os
import stat
import tempfile

from awx_plugins.interfaces._temporary_private_container_api import (  # noqa: WPS436
    get_incontainer_path,
)
from awx_plugins.interfaces._temporary_private_credential_api import (  # noqa: WPS436
    Credential,
    GenericOptionalPrimitiveType,
)
from awx_plugins.interfaces._temporary_private_django_api import (  # noqa: WPS436
    get_vmware_certificate_validation_setting,
)

import yaml


def aws(
    cred: Credential,
    env: dict[str, GenericOptionalPrimitiveType],
    private_data_dir: str,
) -> None:
    env['AWS_ACCESS_KEY_ID'] = cred.get_input('username', default='')
    env['AWS_SECRET_ACCESS_KEY'] = cred.get_input('password', default='')

    if cred.has_input('security_token'):
        env['AWS_SECURITY_TOKEN'] = cred.get_input(
            'security_token', default='',
        )
        env['AWS_SESSION_TOKEN'] = env['AWS_SECURITY_TOKEN']


def gce(
    cred: Credential,
    env: dict[str, GenericOptionalPrimitiveType],
    private_data_dir: str,
) -> str:
    project = cred.get_input('project', default='')
    username = cred.get_input('username', default='')

    json_cred = {
        'type': 'service_account',
        'private_key': cred.get_input(
            'ssh_key_data',
            default='',
        ),
        'client_email': username,
        'project_id': project,
    }
    if 'INVENTORY_UPDATE_ID' not in env:
        env['GCE_EMAIL'] = username
        env['GCE_PROJECT'] = project
    json_cred['token_uri'] = (  # noqa: S105; not a password
        'https://oauth2.googleapis.com/token'
    )

    handle, path = tempfile.mkstemp(dir=os.path.join(private_data_dir, 'env'))
    f = os.fdopen(handle, 'w')
    json.dump(json_cred, f, indent=2)
    f.close()
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    container_path = get_incontainer_path(path, private_data_dir)
    env['GCE_CREDENTIALS_FILE_PATH'] = container_path
    env['GCP_SERVICE_ACCOUNT_FILE'] = container_path
    env['GOOGLE_APPLICATION_CREDENTIALS'] = container_path

    # Handle env variables for new module types.
    # This includes gcp_compute inventory plugin and
    # all new gcp_* modules.
    env['GCP_AUTH_KIND'] = 'serviceaccount'
    env['GCP_PROJECT'] = project
    env['GCP_ENV_TYPE'] = 'tower'
    return path


def azure_rm(
    cred: Credential,
    env: dict[str, GenericOptionalPrimitiveType],
    private_data_dir: str,
) -> None:
    client = cred.get_input('client', default='')
    tenant = cred.get_input('tenant', default='')

    env['AZURE_SUBSCRIPTION_ID'] = cred.get_input('subscription', default='')

    if client and tenant:
        env['AZURE_CLIENT_ID'] = client
        env['AZURE_TENANT'] = tenant
        env['AZURE_SECRET'] = cred.get_input('secret', default='')
    else:
        env['AZURE_AD_USER'] = cred.get_input('username', default='')
        env['AZURE_PASSWORD'] = cred.get_input('password', default='')

    if cred.has_input('cloud_environment'):
        env['AZURE_CLOUD_ENVIRONMENT'] = cred.get_input('cloud_environment')


def vmware(
    cred: Credential,
    env: dict[str, GenericOptionalPrimitiveType],
    private_data_dir: str,
) -> None:
    env['VMWARE_USER'] = cred.get_input('username', default='')
    env['VMWARE_PASSWORD'] = cred.get_input('password', default='')
    env['VMWARE_HOST'] = cred.get_input('host', default='')
    env['VMWARE_VALIDATE_CERTS'] = str(
        get_vmware_certificate_validation_setting(),
    )


def _openstack_data(cred: Credential):
    openstack_auth = dict(
        auth_url=cred.get_input('host', default=''),
        username=cred.get_input('username', default=''),
        password=cred.get_input('password', default=''),
        project_name=cred.get_input('project', default=''),
    )
    if cred.has_input('project_domain_name'):
        openstack_auth['project_domain_name'] = cred.get_input(
            'project_domain_name', default='',
        )
    if cred.has_input('domain'):
        openstack_auth['domain_name'] = cred.get_input('domain', default='')
    verify_state = cred.get_input('verify_ssl', default=True)

    openstack_data = {
        'clouds': {
            'devstack': {
                'auth': openstack_auth,
                'verify': verify_state,
            },
        },
    }

    if cred.has_input('region'):
        openstack_data['clouds']['devstack']['region_name'] = cred.get_input(
            'region', default='',
        )

    return openstack_data


def openstack(
    cred: Credential,
    env: dict[str, GenericOptionalPrimitiveType],
    private_data_dir: str,
) -> None:
    handle, path = tempfile.mkstemp(dir=os.path.join(private_data_dir, 'env'))
    f = os.fdopen(handle, 'w')
    openstack_data = _openstack_data(cred)
    yaml.safe_dump(
        openstack_data,
        f,
        default_flow_style=False,
        allow_unicode=True,
    )
    f.close()
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    env['OS_CLIENT_CONFIG_FILE'] = get_incontainer_path(path, private_data_dir)


def kubernetes_bearer_token(
        cred: Credential,
        env: dict[str, GenericOptionalPrimitiveType],
        private_data_dir: str,
) -> None:
    env['K8S_AUTH_HOST'] = cred.get_input('host', default='')
    env['K8S_AUTH_API_KEY'] = cred.get_input('bearer_token', default='')
    if cred.get_input('verify_ssl') and cred.has_input('ssl_ca_cert'):
        env['K8S_AUTH_VERIFY_SSL'] = 'True'
        handle, path = tempfile.mkstemp(
            dir=os.path.join(private_data_dir, 'env'),
        )
        with os.fdopen(handle, 'w') as f:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
            f.write(str(cred.get_input('ssl_ca_cert')))
        env['K8S_AUTH_SSL_CA_CERT'] = get_incontainer_path(
            path, private_data_dir,
        )
    else:
        env['K8S_AUTH_VERIFY_SSL'] = 'False'


def terraform(
    cred: Credential,
    env: dict[str, GenericOptionalPrimitiveType],
    private_data_dir: str,
) -> None:
    handle, path = tempfile.mkstemp(dir=os.path.join(private_data_dir, 'env'))
    with os.fdopen(handle, 'w') as f:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        f.write(str(cred.get_input('configuration')))
    env['TF_BACKEND_CONFIG_FILE'] = get_incontainer_path(
        path, private_data_dir,
    )
    # Handle env variables for GCP account credentials
    if cred.has_input('gce_credentials'):
        handle, path = tempfile.mkstemp(
            dir=os.path.join(private_data_dir, 'env'),
        )
        with os.fdopen(handle, 'w') as f:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
            f.write(str(cred.get_input('gce_credentials')))
        env['GOOGLE_BACKEND_CREDENTIALS'] = get_incontainer_path(
            path, private_data_dir,
        )
