# Copyright 2021 IBM Corp. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
End2end tests for user patterns (on CPCs in DPM mode).

These tests do not change any existing user patterns, but create,
modify and delete test user patterns.
"""

from __future__ import absolute_import, print_function

import warnings
import pytest
from requests.packages import urllib3

import zhmcclient
# pylint: disable=line-too-long,unused-import
from zhmcclient.testutils import hmc_definition, hmc_session  # noqa: F401, E501
# pylint: enable=line-too-long,unused-import

from .utils import pick_test_resources, runtest_find_list, TEST_PREFIX, \
    skip_warn

urllib3.disable_warnings()

# Properties in minimalistic UserPattern objects (e.g. find_by_name())
UPATT_MINIMAL_PROPS = ['element-uri', 'name']

# Properties in UserPattern objects returned by list() without full props
UPATT_LIST_PROPS = ['element-uri', 'name', 'type']

# Properties whose values can change between retrievals of UserPattern objects
UPATT_VOLATILE_PROPS = []


def test_upatt_find_list(hmc_session):  # noqa: F811
    # pylint: disable=redefined-outer-name
    """
    Test list(), find(), findall().
    """
    client = zhmcclient.Client(hmc_session)
    console = client.consoles.console
    hd = hmc_session.hmc_definition

    api_version = client.query_api_version()
    hmc_version = api_version['hmc-version']
    hmc_version_info = tuple(map(int, hmc_version.split('.')))
    if hmc_version_info < (2, 13, 0):
        skip_warn("HMC {h} of version {v} does not yet support user patterns".
                  format(h=hd.host, v=hmc_version))

    # Pick the user patterns to test with
    upatt_list = console.user_patterns.list()
    if not upatt_list:
        skip_warn("No user patterns defined on HMC {h}".format(h=hd.host))
    upatt_list = pick_test_resources(upatt_list)

    for upatt in upatt_list:
        print("Testing with user pattern {p!r}".format(p=upatt.name))
        runtest_find_list(
            hmc_session, console.user_patterns, upatt.name, 'name',
            'element-uri', UPATT_VOLATILE_PROPS, UPATT_MINIMAL_PROPS,
            UPATT_LIST_PROPS)


def test_upatt_crud(hmc_session):  # noqa: F811
    # pylint: disable=redefined-outer-name
    """
    Test create, read, update and delete a user pattern.
    """
    client = zhmcclient.Client(hmc_session)
    console = client.consoles.console
    hd = hmc_session.hmc_definition

    api_version = client.query_api_version()
    hmc_version = api_version['hmc-version']
    hmc_version_info = tuple(map(int, hmc_version.split('.')))
    if hmc_version_info < (2, 13, 0):
        skip_warn("HMC {h} of version {v} does not yet support user patterns".
                  format(h=hd.host, v=hmc_version))

    upatt_name = TEST_PREFIX + ' test_upatt_crud upatt1'
    upatt_name_new = upatt_name + ' new'

    # Ensure a clean starting point for this test
    try:
        upatt = console.user_patterns.find(name=upatt_name)
    except zhmcclient.NotFound:
        pass
    else:
        warnings.warn(
            "Deleting test user pattern from previous run: {p!r}".
            format(p=upatt_name), UserWarning)
        upatt.delete()

    # Pick a template user to be the template user for the user pattern
    template_users = console.users.findall(type='template')
    if not template_users:
        skip_warn("No template users on HMC {h}".format(h=hd.host))
    template_user = template_users[0]

    # Test creating the user pattern

    upatt_input_props = {
        'name': upatt_name,
        'description': 'Test user pattern for zhmcclient end2end tests',
        'pattern': TEST_PREFIX + ' test_upatt_crud .+',
        'type': 'regular-expression',
        'retention-time': 180,
        'user-template-uri': template_user.uri,  # required until z13
    }
    upatt_auto_props = {}

    # The code to be tested
    try:
        upatt = console.user_patterns.create(upatt_input_props)
    except zhmcclient.HTTPError as exc:
        if exc.http_status == 403 and exc.reason == 1:
            skip_warn("HMC userid {u!r} is not authorized for task "
                      "'Manage User Patterns' on HMC {h}".
                      format(u=hd.userid, h=hd.host))
        else:
            raise

    for pn, exp_value in upatt_input_props.items():
        assert upatt.properties[pn] == exp_value, \
            "Unexpected value for property {!r}".format(pn)
    upatt.pull_full_properties()
    for pn, exp_value in upatt_input_props.items():
        assert upatt.properties[pn] == exp_value, \
            "Unexpected value for property {!r}".format(pn)
    for pn, exp_value in upatt_auto_props.items():
        assert upatt.properties[pn] == exp_value, \
            "Unexpected value for property {!r}".format(pn)

    # Test updating a property of the user pattern

    new_desc = "Updated user pattern description."

    # The code to be tested
    upatt.update_properties(dict(description=new_desc))

    assert upatt.properties['description'] == new_desc
    upatt.pull_full_properties()
    assert upatt.properties['description'] == new_desc

    # Test renaming the user pattern

    # The code to be tested
    upatt.update_properties(dict(name=upatt_name_new))

    assert upatt.properties['name'] == upatt_name_new
    upatt.pull_full_properties()
    assert upatt.properties['name'] == upatt_name_new
    with pytest.raises(zhmcclient.NotFound):
        console.user_patterns.find(name=upatt_name)

    # Test deleting the user pattern

    # The code to be tested
    upatt.delete()

    with pytest.raises(zhmcclient.NotFound):
        console.user_patterns.find(name=upatt_name_new)
