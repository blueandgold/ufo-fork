"""Test user module functionality."""
from mock import MagicMock
from mock import patch
import os

import flask
from flask.ext.testing import TestCase
from googleapiclient import errors
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
import unittest
from werkzeug.datastructures import MultiDict
from werkzeug.datastructures import ImmutableMultiDict

from . import app
from . import db
# I practically have to shorten this name so every single line doesn't go
# over. If someone can't understand, they can use ctrl+f to look it up here.
from . import google_directory_service as gds
from . import models
from . import oauth
from . import user

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

FAKE_EMAILS_AND_NAMES = [
  {'email': 'foo@aol.com', 'name': 'joe'},
  {'email': 'bar@yahoo.com', 'name': 'bob'},
  {'email': 'baz@gmail.com', 'name': 'mark'}
]
FAKE_DIRECTORY_USER_ARRAY = []
for x in range(0, len(FAKE_EMAILS_AND_NAMES)):
  fake_add_user = {}
  fake_add_user['primaryEmail'] = FAKE_EMAILS_AND_NAMES[x]['email']
  fake_add_user['name'] = {}
  fake_add_user['name']['fullName'] = FAKE_EMAILS_AND_NAMES[x]['name']
  fake_add_user['email'] = FAKE_EMAILS_AND_NAMES[x]['email']
  fake_add_user['role'] = 'MEMBER'
  fake_add_user['type'] = 'USER'
  FAKE_DIRECTORY_USER_ARRAY.append(fake_add_user)

FAKE_CREDENTIALS = 'Look at me. I am a credential!'

class UserTest(TestCase):

  """Test user class functionality."""

  def create_app(self):
    app.config.from_object('config.TestConfiguration')
    return app

  def setUp(self):
    """Setup test app on which to call handlers and db to query."""
    db.create_all()

    self.config = models.Config()
    self.config.isConfigured = True
    self.config.id = 0

    self.config.Add()

  def tearDown(self):
    """Teardown the test db and instances."""
    db.session.delete(self.config)
    db.session.commit()
    db.session.close()

  @patch.object(models.User, 'GetAll')
  def testListUsersHandler(self, mock_get_all):
    """Test the list user handler displays users from the database."""
    mock_users = []
    for x in range(0, len(FAKE_EMAILS_AND_NAMES)):
      mock_user = MagicMock(id=x + 1, email=FAKE_EMAILS_AND_NAMES[x]['email'],
                            name=FAKE_EMAILS_AND_NAMES[x]['name'])
      mock_users.append(mock_user)
    mock_get_all.return_value = mock_users

    resp = self.client.get(flask.url_for('user_list'))
    user_list_output = resp.data

    self.assertEquals('Add Users' in user_list_output, True)
    click_user_string = 'Click a user below to view more details.'
    self.assertEquals(click_user_string in user_list_output, True)

    for x in range(0, len(FAKE_EMAILS_AND_NAMES)):
      self.assertEquals(FAKE_EMAILS_AND_NAMES[x]['email'] in user_list_output,
                        True)
      details_link = flask.url_for('user_details', user_id=mock_users[x].id)
      self.assertEquals(details_link in user_list_output, True)

  @patch.object(user, '_RenderUserAdd')
  def testAddUsersGetHandler(self, mock_render):
    """Test the add users get handler returns _RenderUserAdd's result."""
    return_text = '<html>something here </html>'
    mock_render.return_value = return_text
    resp = self.client.get(flask.url_for('add_user'))

    self.assertEquals(resp.data, return_text)

  @patch('flask.render_template')
  @patch.object(oauth, 'getSavedCredentials')
  def testAddUsersGetNoCredentials(self, mock_get_saved_credentials,
                                  mock_render_template):
    """Test add user get should display an error when oauth isn't set."""
    mock_get_saved_credentials.return_value = None
    mock_render_template.return_value = ''

    response = self.client.get(flask.url_for('add_user'))

    args, kwargs = mock_render_template.call_args
    self.assertEquals('add_user.html', args[0])
    self.assertEquals([], kwargs['directory_users'])
    self.assertEquals(kwargs['error'] is not None, True)

  @patch('flask.render_template')
  @patch.object(oauth, 'getSavedCredentials')
  @patch.object(gds.GoogleDirectoryService, '__init__')
  def testAddUsersGetNoParam(self, mock_ds, mock_get_saved_credentials,
                            mock_render_template):
    """Test add user get should display no users on initial get."""
    mock_get_saved_credentials.return_value = FAKE_CREDENTIALS
    mock_ds.return_value = None
    mock_render_template.return_value = ''

    response = self.client.get(flask.url_for('add_user'))

    args, kwargs = mock_render_template.call_args
    self.assertEquals('add_user.html', args[0])
    self.assertEquals([], kwargs['directory_users'])

  @patch('flask.render_template')
  @patch.object(oauth, 'getSavedCredentials')
  @patch.object(gds.GoogleDirectoryService, 'GetUsersByGroupKey')
  @patch.object(gds.GoogleDirectoryService, '__init__')
  def testAddUsersGetWithGroup(self, mock_ds, mock_get_by_key,
                              mock_get_saved_credentials,
                              mock_render_template):
    """Test add user get should display users from a given group."""
    mock_get_saved_credentials.return_value = FAKE_CREDENTIALS
    mock_ds.return_value = None
    # Email address could refer to group or user
    group_key = 'foo@bar.mybusiness.com'
    query_string = '?group_key={0}'.format(group_key)
    mock_get_by_key.return_value = FAKE_DIRECTORY_USER_ARRAY
    mock_render_template.return_value = ''

    response = self.client.get(flask.url_for('add_user') + query_string)

    args, kwargs = mock_render_template.call_args
    self.assertEquals('add_user.html', args[0])
    self.assertEquals(FAKE_DIRECTORY_USER_ARRAY, kwargs['directory_users'])

  @patch('flask.render_template')
  @patch.object(oauth, 'getSavedCredentials')
  @patch.object(gds.GoogleDirectoryService, 'GetUserAsList')
  @patch.object(gds.GoogleDirectoryService, '__init__')
  def testAddUsersGetWithUser(self, mock_ds, mock_get_user,
                             mock_get_saved_credentials,
                             mock_render_template):
    """Test add user get should display a given user as requested."""
    mock_get_saved_credentials.return_value = FAKE_CREDENTIALS
    mock_ds.return_value = None
    # Email address could refer to group or user
    user_key = 'foo@bar.mybusiness.com'
    query_string = '?user_key={0}'.format(user_key)
    mock_get_user.return_value = FAKE_DIRECTORY_USER_ARRAY
    mock_render_template.return_value = ''

    response = self.client.get(flask.url_for('add_user') + query_string)

    args, kwargs = mock_render_template.call_args
    self.assertEquals('add_user.html', args[0])
    self.assertEquals(FAKE_DIRECTORY_USER_ARRAY, kwargs['directory_users'])

  @patch('flask.render_template')
  @patch.object(oauth, 'getSavedCredentials')
  @patch.object(gds.GoogleDirectoryService, 'GetUsers')
  @patch.object(gds.GoogleDirectoryService, '__init__')
  def testAddUsersGetWithAll(self, mock_ds, mock_get_users,
                            mock_get_saved_credentials,
                            mock_render_template):
    """Test add user get should display all users in a domain."""
    mock_get_saved_credentials.return_value = FAKE_CREDENTIALS
    mock_ds.return_value = None
    query_string = '?get_all=true'
    mock_get_users.return_value = FAKE_DIRECTORY_USER_ARRAY
    mock_render_template.return_value = ''

    response = self.client.get(flask.url_for('add_user') + query_string)

    args, kwargs = mock_render_template.call_args
    self.assertEquals('add_user.html', args[0])
    self.assertEquals(FAKE_DIRECTORY_USER_ARRAY, kwargs['directory_users'])

  @patch('flask.render_template')
  @patch.object(oauth, 'getSavedCredentials')
  @patch.object(gds.GoogleDirectoryService, '__init__')
  def testAddUsersGetWithError(self, mock_ds, mock_get_saved_credentials,
                              mock_render_template):
    """Test add users get handler fails gracefully with an error."""
    mock_get_saved_credentials.return_value = FAKE_CREDENTIALS
    fake_status = '404'
    fake_response = MagicMock(status=fake_status)
    fake_content = b'some error content'
    fake_error = errors.HttpError(fake_response, fake_content)
    mock_ds.side_effect = fake_error
    mock_render_template.return_value = ''

    response = self.client.get(flask.url_for('add_user'))

    args, kwargs = mock_render_template.call_args
    self.assertEquals('add_user.html', args[0])
    self.assertEquals([], kwargs['directory_users'])
    self.assertEquals(fake_error, kwargs['error'])

  @patch.object(models.User, 'Add')
  def testAddUsersPostHandler(self, mock_add):
    """Test the add users post handler calls to insert the specified users."""
    mock_users = []
    data = MultiDict()
    for x in range(0, len(FAKE_EMAILS_AND_NAMES)):
      mock_user = {}
      mock_user['primaryEmail'] = FAKE_EMAILS_AND_NAMES[x]['email']
      mock_user['name'] = {}
      mock_user['name']['fullName'] = FAKE_EMAILS_AND_NAMES[x]['name']
      mock_users.append(mock_user)
      data.add('selected_user', json.dumps(mock_user))

    data = ImmutableMultiDict(data)

    response = self.client.post(flask.url_for('add_user'), data=data,
                                follow_redirects=False)

    self.assert_redirects(response, flask.url_for('user_list'))
    for x in range(0, len(FAKE_EMAILS_AND_NAMES)):
      mock_add.assert_any_call()

  @patch.object(models.User, 'Add')
  def testAddUsersPostManualHandler(self, mock_add):
    """Test add users manually calls to insert the specified user."""
    data = {}
    data['manual'] = True
    data['user_email'] = FAKE_EMAILS_AND_NAMES[0]['email']
    data['user_name'] = FAKE_EMAILS_AND_NAMES[0]['name']

    response = self.client.post(flask.url_for('add_user'), data=data,
                                follow_redirects=False)

    self.assert_redirects(response, flask.url_for('user_list'))
    mock_add.assert_called_once_with()


if __name__ == '__main__':
  unittest.main()
