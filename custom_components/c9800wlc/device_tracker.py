"""Support for Cisco C9800 WLC."""

from __future__ import annotations

import logging
# import re
import xmltodict
from ncclient import manager
from ncclient.operations import RPCError
import lxml.etree as et
# from pexpect import pxssh
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD, default=""): cv.string,
            vol.Optional(CONF_PORT, default=830): cv.port,
        }
    )
)

PAYLOAD = [
'''
<get xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <filter>
    <client-oper-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-wireless-client-oper">
      <common-oper-data/>
      <common-oper-data>
        <client-mac/>
      </common-oper-data>
    </client-oper-data>
  </filter>
  <with-defaults xmlns="urn:ietf:params:xml:ns:yang:ietf-netconf-with-defaults">report-all</with-defaults>
</get>
''',
]


def get_scanner(hass: HomeAssistant, config: ConfigType) -> CiscoDeviceScanner | None:
    """Validate the configuration and return a Cisco scanner."""
    scanner = CiscoDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None

class CiscoDeviceScanner(DeviceScanner):
    """Class which queries a wireless router running Cisco IOS firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.port = config.get(CONF_PORT)
        self.password = config[CONF_PASSWORD]

        self.last_results = {}

        self.success_init = self._update_info()
        _LOGGER.info("Initialized cisco_ios scanner")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results
    def _update_info(self):
        """Ensure the information from the Cisco router is up to date.

        Returns boolean if scanning successful.
        """
        with manager.connect(host=self.host,
                                port=self.port,
                                username=self.username,
                                password=self.password,
                                timeout=90,
                                hostkey_verify=False,
                                device_params={'name': 'csr'}) as m:
                output = []
                # execute netconf operation
                for rpc in PAYLOAD:
                    try:
                        response = m.dispatch(et.fromstring(rpc))
                        data = response.xml
                    except RPCError as e:
                        data = e.xml
                        pass
                    except Exception as e:
                        _LOGGER.error(str(e))
                        return False

                    try:
                        response_dict = xmltodict.parse(data)

                        clients_dict = response_dict['rpc-reply']['data']['client-oper-data']['common-oper-data']
                        for client in clients_dict:
                            if len(client)>2:
                                if client['username'] != None:
                                    output.append(client['username'])
                            output.append(client['client-mac'])
                        self.last_results = output
                        return True

                    except Exception as e:
                        _LOGGER.error(str(e))
                        return False


             
                return False