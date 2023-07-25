# -*- coding: utf-8 -*-

# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# This script is part of our solar monitoring project. See:
# https://github.com/greiginsydney/Get-EnphaseData-v7.py
# https://greiginsydney.com/get-enphasedata-v7-py
# https://greiginsydney.com/category/prtg/

# from *WINDOWS* call as python ./Get-EnphaseData.py '{\"host\":\"<IP>"}'
# Get-EnphaseData\python> &"C:\Program Files (x86)\PRTG Network Monitor\python\python" ./Get-EnphaseData.py '{\"host\":\"http://<IP>"}'

import json
import os
import re           # for the regex replacement (sub)
import requests     # for the web call to Enphase
import sys
from requests.auth import HTTPDigestAuth

#TY SO: https://stackoverflow.com/a/32282390/13102734
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

USER = 'yourEnvoyUsername@yourDomain.com' # These are the credentials you use to login to the Enphase website
PASSWORD = 'abscdg123456789...etc'        # "
SERIAL_NUMBER = '123456789098765432'      # Get this from the Envoy app: Menu / system / Devices / Gateway. It's the "SN:"

USER_HOME =  os.path.expanduser('~')
#TOKEN_FILE  = os.path.join(os.getcwd(), 'envoy_token.json')
TOKEN_FILE  = os.path.join(USER_HOME, 'envoy_token.json')


def main():
    # Let's make sure we have a token first, and that it's saved to the TOKEN_FILE
    try:
        if not os.path.isfile(TOKEN_FILE):
            with open(TOKEN_FILE, 'w') as tokenFile:
                tokenFile.write('')
        with open(TOKEN_FILE, 'r') as tokenFile:
            authToken = tokenFile.read()
        if authToken is None or authToken == '':
            #print('authToken is empty. Off to Enphase for one')
            authToken, errMsg = getToken(None)
            if errMsg:
                result = {'prtg': {'text' : 'Token creation error', 'error' : errMsg}}
                print(json.dumps(result))
                sys.exit(1)
    except Exception as e:
        result = {'prtg': {'text' : 'Unhandled token setup error', 'error' : "%s" % str(e)}}
        print(json.dumps(result))
        sys.exit(1)
    
    try:
        url = ''
        if len(sys.argv) > 1:
            args = json.loads(sys.argv[1])
            # Check for 'host' and 'params' keys in the passed JSON, with params taking precedence:
            # (We strip any http or https prefix, but there's no other validation)
            for i in ("host", "params"):
                if args.get(i):
                    url = re.sub("https?:", "", args[i]).strip().strip('/')
            result = {'prtg': {'text' : "This sensor queries %s" % url}}
        if len(url) == 0:
            result = {'prtg': {'text' : 'Insufficient or bad arguments', 'error' : {'args' : sys.argv}}}
            print(json.dumps(result))
            sys.exit(1)
        
        try:
            if authToken is None or authToken == '':
                result = {'prtg': {'text' : 'No token', 'error' : 'None'}}
                print(json.dumps(result))
                sys.exit(1)
            response = None
            query = "https://" + url + "/api/v1/production/inverters"
            #query = "https://" + url + "/auth/check_jwt"
            headers = {"Authorization": ("Bearer " + str(authToken))}
            response = requests.get(query, timeout=20, verify=False, headers=headers)
            response.raise_for_status() #Throws a HTTPError if we didn't receive a 2xx response
            jsonResponse = json.loads(response.text)
            if jsonResponse:
                result['prtg'].update({'result': []})

                result['prtg']['result'].append(
                    {'Channel' : 'panel count',
                    'Value' : len(jsonResponse),
                    'Unit' : 'Custom',
                    'CustomUnit' : 'Count',
                    'Float' : 0,
                    'ShowChart' : 0,
                    'ShowTable' : 0,
                    'primary' : 1
                    })

                panelMax = 0
                panelMin = 10000

                for eachPanel in jsonResponse:
                    result['prtg']['result'].append(
                        {'Channel' : eachPanel['serialNumber'],
                        'Value' : eachPanel['lastReportWatts'],
                        'Unit' : 'Custom',
                        'CustomUnit' : 'Watts',
                        'Float' : 0,
                        'ShowChart' : 1,
                        'ShowTable' : 1
                        })
                    if eachPanel['lastReportWatts'] > panelMax: panelMax = eachPanel['lastReportWatts']
                    if eachPanel['lastReportWatts'] < panelMin: panelMin = eachPanel['lastReportWatts']

                result['prtg']['result'].append(
                    {'Channel' : 'panel range',
                    'Value' : (panelMax - panelMin),
                    'Unit' : 'Custom',
                    'CustomUnit' : 'Watts',
                    'Float' : 0,
                    'ShowChart' : 0,
                    'ShowTable' : 0,
                    })


        except requests.exceptions.Timeout as e:
            result = {'prtg': {'text' : 'Remote host timeout error', 'error' : "%s" % str(e)}}
        except requests.exceptions.ConnectionError as e:
            result = {'prtg': {'text' : 'Remote host connection error', 'error' : "%s" % str(e)}}
        except requests.exceptions.HTTPError as e:
            result = {'prtg': {'text' : 'Remote host HTTP error', 'error' : "%s" % str(e)}}
        except requests.exceptions.TooManyRedirects as e:
            result = {'prtg': {'text' : 'Remote host Too Many Redirects error', 'error' : "%s" % str(e)}}
        except Exception as e:
            result = {'prtg': {'text' : 'Unhandled error', 'error' : "%s" % str(e)}}

    except Exception as e:
        result = {'prtg': {'text' : 'Python Script execution error', 'error' : "%s" % str(e)}}

    print('')
    print(json.dumps(result))


def getToken(token):
    '''
    This is largely straight out of the Enphase technical brief, with tweaks inspired by
    https://github.com/vk2him/Enphase-Envoy-mqtt-json/blob/main/envoy_to_mqtt_json.py
    '''
    try:
        if token is None or token == '':
            data = {'user[email]': USER, 'user[password]': PASSWORD}
            response = requests.post('https://enlighten.enphaseenergy.com/login/login.json?', data=data)
            if response.ok:
                response_data = json.loads(response.text)
                data = {'session_id': response_data['session_id'], 'serial_num': SERIAL_NUMBER, 'username': USER}
                response = requests.post('https://entrez.enphaseenergy.com/tokens', json=data)
                if response.ok:
                    token = response.text
                    with open(TOKEN_FILE, 'w') as f:
                        f.write(token)
                    return token, None
                else:
                    #Badness
                    htmltext = response.text.rstrip()
                    return None, htmltext
            else:
                htmltext = response.text.rstrip()
                return None, htmltext
        else:
            return token, None

    except Exception as e:
        return None, str(e)


if __name__ == "__main__":
   main()

# References:
# Accessing IQ Gateway local APIs or local UI with token-based authentication:
#  https://enphase.com/download/accessing-iq-gateway-local-apis-or-local-ui-token-based-authentication
# VK2HIM for much of the structure above: https://github.com/vk2him/Enphase-Envoy-mqtt-json/blob/main/envoy_to_mqtt_json.py
# ValueCustomUnits: C:\Program Files (x86)\PRTG Network Monitor\python\Lib\site-packages\prtg\sensor\CustomUnits.py
