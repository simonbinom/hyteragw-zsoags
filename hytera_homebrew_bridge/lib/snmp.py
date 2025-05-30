#!/usr/bin/env python3
import asyncio
import logging
import sys
import warnings
from typing import Union, Literal, Dict

import puresnmp

from hytera_homebrew_bridge.lib.logging_trait import LoggingTrait
from hytera_homebrew_bridge.lib.settings import BridgeSettings
from hytera_homebrew_bridge.lib.utils import octet_string_to_utf8

KNOWN_SNMP_COMMUNITIES = Union[Literal["hytera"], Literal["public"]]
DEFAULT_SNMP_COMMUNITY = "public"


class SNMP(LoggingTrait):
    # in milli-volts (V * 1000)
    OID_PSU_VOLTAGE: str = "iso.3.6.1.4.1.40297.1.2.1.2.1.0"
    # in milli-celsius (C * 1000)
    OID_PA_TEMPERATURE: str = "iso.3.6.1.4.1.40297.1.2.1.2.2.0"
    # voltage ratio on the TX in dB
    OID_VSWR: str = "iso.3.6.1.4.1.40297.1.2.1.2.4.0"
    # Forward power in milli-watt
    OID_TX_FWD_POWER: str = "iso.3.6.1.4.1.40297.1.2.1.2.5.0"
    # Reflected power in milli-watt
    OID_TX_REF_POWER: str = "iso.3.6.1.4.1.40297.1.2.1.2.6.0"
    OID_RSSI_TS1: str = "iso.3.6.1.4.1.40297.1.2.1.2.9.0"
    OID_RSSI_TS2: str = "iso.3.6.1.4.1.40297.1.2.1.2.10.0"

    OID_REPEATER_MODEL: str = "iso.3.6.1.4.1.40297.1.2.4.1.0"
    OID_MODEL_NUMBER: str = "iso.3.6.1.4.1.40297.1.2.4.2.0"
    # string
    OID_FIRMWARE_VERSION: str = "iso.3.6.1.4.1.40297.1.2.4.3.0"
    # Radio Data Version, string
    OID_RCDB_VERSION: str = "iso.3.6.1.4.1.40297.1.2.4.4.0"
    OID_SERIAL_NUMBER: str = "iso.3.6.1.4.1.40297.1.2.4.5.0"
    # callsign
    OID_RADIO_ALIAS: str = "iso.3.6.1.4.1.40297.1.2.4.6.0"
    # integer
    OID_RADIO_ID: str = "iso.3.6.1.4.1.40297.1.2.4.7.0"
    # digital=0, analog=1, mixed=2
    OID_CUR_CHANNEL_MODE: str = "iso.3.6.1.4.1.40297.1.2.4.8.0"
    OID_CUR_CHANNEL_NAME: str = "iso.3.6.1.4.1.40297.1.2.4.9.0"
    # Hz
    OID_TX_FREQUENCE: str = "iso.3.6.1.4.1.40297.1.2.4.10.0"
    # Hz
    OID_RX_FREQUENCE: str = "iso.3.6.1.4.1.40297.1.2.4.11.0"
    # receive=0, transmit=1
    OID_WORK_STATUS: str = "iso.3.6.1.4.1.40297.1.2.4.12.0"
    OID_CUR_ZONE_ALIAS: str = "iso.3.6.1.4.1.40297.1.2.4.13.0"

    READABLE_LABELS = {
        OID_PSU_VOLTAGE: ("PSU Voltage", "%d mV"),
        OID_PA_TEMPERATURE: ("PA Temperature", "%d m°C"),
        OID_VSWR: ("VSWR", "%d dB"),
        OID_TX_FWD_POWER: ("TX Forward Power", "%d mW"),
        OID_TX_REF_POWER: ("TX Reflected Power", "%d mW"),
        OID_RSSI_TS1: ("RSSI TS1", "%d dB"),
        OID_RSSI_TS2: ("RSSI TS2", "%d dB"),
        OID_REPEATER_MODEL: ("Repeater Model", "%s"),
        OID_MODEL_NUMBER: ("Repeater Model Identification", "%s"),
        OID_FIRMWARE_VERSION: ("Repeater Firmware", "%s"),
        OID_RCDB_VERSION: ("Repeater Radio Data (RCDB)", "%s"),
        OID_SERIAL_NUMBER: ("Repeater Serial No.", "%s"),
        OID_RADIO_ALIAS: ("Radio Alias (Callsign)", "%s"),
        OID_RADIO_ID: ("Repeater ID", "%d"),
        OID_CUR_CHANNEL_NAME: ("Current Channel Name", "%s"),
        OID_CUR_CHANNEL_MODE: (
            "Current Channel Zone (0=DIGITAL, 1=ANALOG, 2=MIXED)",
            "%d",
        ),
        OID_TX_FREQUENCE: ("TX Frequence", "%d Hz"),
        OID_RX_FREQUENCE: ("RX Frequence", "%d Hz"),
        OID_WORK_STATUS: ("Work Status (0=RECEIVE, 1=TRANSMIT)", "%d"),
        OID_CUR_ZONE_ALIAS: ("Current Zone Alias", "%s"),
    }

    ALL_STRINGS = (
        OID_REPEATER_MODEL,
        OID_MODEL_NUMBER,
        OID_FIRMWARE_VERSION,
        OID_RCDB_VERSION,
        OID_RADIO_ALIAS,
        OID_CUR_ZONE_ALIAS,
        OID_SERIAL_NUMBER,
        OID_CUR_CHANNEL_NAME,
    )

    ALL_FLOATS = (
        OID_PSU_VOLTAGE,
        OID_VSWR,
        OID_PA_TEMPERATURE,
        OID_TX_FWD_POWER,
        OID_TX_REF_POWER,
    )

    ALL_KNOWN = (
        OID_PSU_VOLTAGE,
        OID_PA_TEMPERATURE,
        OID_VSWR,
        OID_TX_FWD_POWER,
        OID_TX_REF_POWER,
        OID_RSSI_TS1,
        OID_RSSI_TS2,
        OID_REPEATER_MODEL,
        OID_MODEL_NUMBER,
        OID_FIRMWARE_VERSION,
        OID_RCDB_VERSION,
        OID_SERIAL_NUMBER,
        OID_RADIO_ALIAS,
        OID_RADIO_ID,
        OID_CUR_CHANNEL_MODE,
        OID_CUR_CHANNEL_NAME,
        OID_TX_FREQUENCE,
        OID_RX_FREQUENCE,
        OID_WORK_STATUS,
        OID_CUR_ZONE_ALIAS,
    )

    OID_WALK_BASE_1: str = "1.3.6.1.4.1.40297.1.2.4"
    OID_WALK_BASE_2: str = "1.3.6.1.4.1.40297.1.2.1.2"

    async def walk_ip(
        self,
        ip: str,
        settings_storage: BridgeSettings,
        snmp_community: KNOWN_SNMP_COMMUNITIES = DEFAULT_SNMP_COMMUNITY,
        first_try: bool = True,
        timeout_secs: int = 2,
    ) -> Dict[str, any]:
        is_success: bool = False

        snmp_data: Dict[str, any] = {}

        # noinspection PyTypeChecker
        other_community: KNOWN_SNMP_COMMUNITIES = (
            "public" if snmp_community == "hytera" else "hytera"
        )
        client = puresnmp.PyWrapper(
            client=puresnmp.Client(
                ip=ip, credentials=puresnmp.V1(community=snmp_community)
            )
        )

        # noinspection PyBroadException
        try:
            for oid in SNMP.ALL_KNOWN:
                _oid = oid.replace("iso", "1")
                snmp_result = await asyncio.wait_for(
                    fut=client.get(oid=_oid), timeout=timeout_secs
                )

                if oid in SNMP.ALL_STRINGS:
                    snmp_result = octet_string_to_utf8(str(snmp_result, "utf8"))
                elif oid in SNMP.ALL_FLOATS:
                    snmp_result = int.from_bytes(snmp_result, byteorder="big")
                snmp_data[oid] = snmp_result
            is_success = True
        except ConnectionRefusedError:
            self.log_error("SNMP failed, Connection to port 162 was refused")
        except SystemError as se:
            self.log_error("SNMP failed to obtain repeater info")
            self.log_exception(se)
        except (
            asyncio.exceptions.CancelledError,
            puresnmp.exc.Timeout,
            asyncio.exceptions.TimeoutError,
            TimeoutError,
        ) as e:
            if first_try:
                self.log_debug(
                    "Failed with SNMP family %s, trying with %s as well"
                    % (snmp_community, other_community)
                )
                await self.walk_ip(
                    ip=ip,
                    settings_storage=settings_storage,
                    first_try=False,
                    snmp_community=other_community,
                )
            else:
                self.log_error("SNMP failed")
                self.log_exception(e)
        except:
            self.log_exception("Unhandled exception")
            self.log_exception(sys.exc_info())

        if is_success:
            # set data to storage
            for key, value in snmp_data.items():
                settings_storage.hytera_snmp_data[key] = value
            # print from storage
            self.print_snmp_data(settings_storage)

        return snmp_data

    def print_snmp_data(self, settings_storage: BridgeSettings):
        self.log_debug(
            "-------------- REPEATER SNMP CONFIGURATION ----------------------------"
        )
        longest_label = 0
        for key in SNMP.READABLE_LABELS:
            label_len = len(SNMP.READABLE_LABELS.get(key)[0])
            if label_len > longest_label:
                longest_label = label_len

        for key in settings_storage.hytera_snmp_data:
            print_settings = SNMP.READABLE_LABELS.get(key)
            if print_settings:
                value = settings_storage.hytera_snmp_data.get(key)
                self.log_debug(
                    "%s| %s"
                    % (
                        str(print_settings[0]).ljust(longest_label + 5),
                        print_settings[1] % value,
                    )
                )
        self.log_debug(
            "-------------- REPEATER SNMP CONFIGURATION ----------------------------"
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("use as snmp.py <ip of hytera repeater>")
        exit(1)

    logging.basicConfig(level=logging.NOTSET)
    logging.getLogger("puresnmp.transport").setLevel(logging.WARN)

    warnings.filterwarnings("ignore", category=UserWarning, module="puresnmp_plugins")

    settings: BridgeSettings = BridgeSettings(filedata=BridgeSettings.MINIMAL_SETTINGS)
    asyncio.run(SNMP().walk_ip(sys.argv[1], settings_storage=settings))
