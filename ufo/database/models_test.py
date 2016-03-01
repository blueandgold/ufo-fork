"""Test for models module functionality."""

import os
import unittest

from Crypto.PublicKey import RSA
from mock import MagicMock
from mock import patch

from ufo import base_test
from ufo.database import models
from ufo.handlers import user


FAKE_PRIVATE_KEY = 'fakePrivateKey'


class UserTest(base_test.BaseTest):
  """Test for user model class functionality."""

  def testGenerateKeyPair(self):
    """Whether the generated key_pair is valid, and with correct size."""
    user = models.User()
    rsa_public_key = RSA.importKey(user.public_key)
    rsa_private_key = RSA.importKey(user.private_key)

    self.assertEqual(2048, rsa_public_key.size() + 1)
    self.assertEqual(2048, rsa_private_key.size() + 1)

    message = os.urandom(8)
    encrypted_message = rsa_public_key.encrypt(message, 12345)
    self.assertEqual(message, rsa_private_key.decrypt(encrypted_message))

  def testRegenerateKeyPair(self):
    """Whether a new key pair is generated that does not match the old one."""
    user = models.User()
    original_public_key = user.public_key
    original_private_key = user.private_key

    user.regenerate_key_pair()
    self.assertNotEqual(original_public_key, user.public_key)
    self.assertNotEqual(original_private_key, user.private_key)

  def testUserToDict(self):
    """Whether the necessary fields match in a dictionary representation."""
    user = models.User()
    user.is_key_revoked = False
    user_dict = user.to_dict()

    self.assertEqual(user_dict['email'], user.email)
    self.assertEqual(user_dict['name'], user.name)
    self.assertEqual(user_dict['private_key'], user.private_key)
    self.assertEqual(user_dict['public_key'], user.public_key)
    self.assertEqual(user_dict['access'], models.NOT_REVOKED_TEXT)

    user.is_key_revoked = True
    user_dict = user.to_dict()
    self.assertEqual(user_dict['access'], models.REVOKED_TEXT)


class ProxyServerTest(base_test.BaseTest):
  """Test for proxy server model class functionality."""

  def testProxyServerToDict(self):
    """Whether the necessary fields match in a dictionary representation."""
    server = models.ProxyServer()
    server.ip_address = '127.0.0.0'
    server.name = 'foo test name'
    temp_key = RSA.generate(2048)
    server.read_public_key_from_file_contents(
        temp_key.publickey().exportKey('OpenSSH'))
    server.read_private_key_from_file_contents(temp_key.exportKey('PEM'))
    server_dict = server.to_dict()

    self.assertEqual(server_dict['id'], server.id)
    self.assertEqual(server_dict['ip_address'], server.ip_address)
    self.assertEqual(server_dict['name'], server.name)
    self.assertEqual(server_dict['public_key'], server.get_public_key_as_authorization_file_string())
    self.assertIn('private_key', server_dict)


class ConfigTest(base_test.BaseTest):
  """Test for config model class functionality."""

  def testConfigToDict(self):
    """Whether the necessary fields match in a dictionary representation."""

    config = models.Config()
    config.isConfigured = True
    config.credentials = 'fake credential'
    config.domain = 'fake domain'
    config.dv_content = 'fake dv content'
    config.proxy_server_validity = True
    config.network_jail_until_google_auth = True
    config_dict = config.to_dict()

    self.assertEqual(config_dict['is_configured'], config.isConfigured)
    self.assertEqual(config_dict['credentials'], config.credentials)
    self.assertEqual(config_dict['domain'], config.domain)
    self.assertEqual(config_dict['dv_content'], config.dv_content)
    self.assertEqual(config_dict['proxy_server_validity'],
                     config.proxy_server_validity)
    self.assertEqual(config_dict['network_jail_until_google_auth'],
                     config.network_jail_until_google_auth)
    

if __name__ == '__main__':
  unittest.main()