import StringIO

from Crypto.PublicKey import RSA
from paramiko import hostkeys
from paramiko import pkey

import ufo
from ufo.services import ssh_client

LONG_STRING_LENGTH = 1024
REVOKED_TEXT = 'Access Disabled'
NOT_REVOKED_TEXT = 'Access Enabled'


class Model(ufo.db.Model):
  """Helpful functions for the database models

  Most method implementations are taken from
  https://github.com/sloria/cookiecutter-flask"""
  __abstract__ = True

  def update(self, commit=True, **kwargs):
    for attr, value in kwargs.items():
      setattr(self, attr, value)
    return commit and self.save() or self

  def save(self, commit=True):
    ufo.db.session.add(self)
    if commit:
      ufo.db.session.commit()
    return self

  def delete(self, commit=True):
    ufo.db.session.delete(self)
    return commit and ufo.db.session.commit()

  def to_dict(self):
    return {}

  @classmethod
  def get_items_as_list_of_dict(cls):
    items = cls.query.all()
    to_return = []
    for item in items:
      to_return.append(item.to_dict())
    return to_return


class Config(Model):
  """Class for anything that needs to be stored as a singleton for the site
  configuration
  """
  __tablename__ = 'config'

  id = ufo.db.Column(ufo.db.Integer, primary_key=True)

  isConfigured = ufo.db.Column(ufo.db.Boolean(), default=False)

  credentials = ufo.db.Column(ufo.db.Text())
  domain = ufo.db.Column(ufo.db.String(LONG_STRING_LENGTH))
  dv_content = ufo.db.Column(ufo.db.String(LONG_STRING_LENGTH))
  proxy_server_validity = ufo.db.Column(ufo.db.Boolean(), default=False)
  network_jail_until_google_auth = ufo.db.Column(ufo.db.Boolean(),
                                                 default=False)

  def to_dict(self):
    """Get the config as a dict.

      Returns: A dictionary of the config.
    """
    return {
      'is_configured': self.isConfigured,
      'credentials': self.credentials,
      'domain': self.domain,
      'dv_content': self.dv_content,
      'proxy_server_validity': self.proxy_server_validity,
      'network_jail_until_google_auth': self.network_jail_until_google_auth,
    }


class User(Model):
  """Class for information about the users of the proxy servers
  """
  __tablename__ = "user"

  id = ufo.db.Column(ufo.db.Integer, primary_key=True)

  email = ufo.db.Column(ufo.db.String(LONG_STRING_LENGTH))
  name = ufo.db.Column(ufo.db.String(LONG_STRING_LENGTH))
  private_key = ufo.db.Column(ufo.db.LargeBinary())
  public_key = ufo.db.Column(ufo.db.LargeBinary())
  is_key_revoked = ufo.db.Column(ufo.db.Boolean(), default=False)

  def __init__(self, **kwargs):
    super(User, self).__init__(**kwargs)

    self.regenerate_key_pair()

  @staticmethod
  def _GenerateKeyPair():
    """Generate a private and public key pair in base64.

    Returns:
      key_pair: A dictionary with private_key and public_key in b64 value.
    """
    rsa_key = RSA.generate(2048)
    private_key = rsa_key.exportKey()
    public_key = rsa_key.publickey().exportKey()

    return {
        'private_key': private_key,
        'public_key': public_key
    }

  def regenerate_key_pair(self):
    key_pair = User._GenerateKeyPair()
    self.private_key = key_pair['private_key']
    self.public_key = key_pair['public_key']

  def to_dict(self):
    return {
      'email': self.email,
      'name': self.name,
      'private_key': self.private_key,
      'public_key': self.public_key,
      'access': REVOKED_TEXT if self.is_key_revoked else NOT_REVOKED_TEXT,
    }


class ProxyServer(Model):
  """Class for information about the proxy servers
  """
  __tablename__ = "proxyserver"

  id = ufo.db.Column(ufo.db.Integer, primary_key=True)

  ip_address = ufo.db.Column(ufo.db.String(LONG_STRING_LENGTH))
  name = ufo.db.Column(ufo.db.String(LONG_STRING_LENGTH))
  ssh_private_key = ufo.db.Column(ufo.db.LargeBinary())
  ssh_private_key_type = ufo.db.Column(ufo.db.String(LONG_STRING_LENGTH))
  host_public_key = ufo.db.Column(ufo.db.LargeBinary())
  host_public_key_type = ufo.db.Column(ufo.db.String(LONG_STRING_LENGTH))

  def read_private_key_from_file_contents(self, contents):
    pkey_instance = pkey.PKey()
    for key_type, key_tag in ssh_client.SSHClient.key_type_to_tag_map.iteritems():
      if ('BEGIN ' + key_tag + ' PRIVATE KEY') not in contents:
        continue

      # Using the private implementation is, unfortunately, the best way to
      # handle this.  If there are ever concerns about this, we can always
      # write a simplified parser
      self.ssh_private_key = pkey_instance._read_private_key(
          key_tag,
          StringIO.StringIO(contents))
      self.ssh_private_key_type = key_type

      return

    raise Exception("Unrecognized private key file")

  def read_public_key_from_file_contents(self, contents):
    try:
      # this should be from a public key file which will not contain the actual
      # host part of the "line"
      host_key_entry = hostkeys.HostKeyEntry.from_line('0.0.0.0 ' + contents)
    except:
      # might be passing in a line from a host file
      host_key_entry = hostkeys.HostKeyEntry.from_line(contents)

    self.host_public_key_type = host_key_entry.key.get_name()
    self.host_public_key = host_key_entry.key.asbytes()

  def get_public_key_as_authorization_file_string(self):
    """Creates an output-able string of the public key for the server.

    Returns:
      A string of the public key for this proxy server.
    """
    public_key = ssh_client.SSHClient.public_key_data_to_object(
        self.host_public_key_type,
        self.host_public_key)
    return public_key.get_name() + ' ' + public_key.get_base64()


  def to_dict(self):
    private_key = ssh_client.SSHClient.private_key_data_to_object(
        self.ssh_private_key_type,
        self.ssh_private_key)
    private_key_file = StringIO.StringIO()
    private_key.write_private_key(private_key_file)
    private_key_text = private_key_file.getvalue()

    return {
      "id": self.id,
      "name": self.name,
      "ip_address": self.ip_address,
      "public_key": self.get_public_key_as_authorization_file_string(),
      "private_key": private_key_text,
      }