
import smtplib
import time
import datetime
import json
import os
from dateutil.parser import parse
import requests


#CONSUL = "http://localhost:8500/v1/"
CONSUL = os.environ['CONSUL_SERVER']

DURATION_URL = "/v1/kv/alerting/duration"

STATE_URL = "/v1/kv/alerting/state"

MAILSERVER_URL = "/v1/kv/alerting/mailserver?raw"

CHECKS_URL = "/v1/agent/checks"


def post_url(url, data=None):
    response = requests.put(url, json.dumps(data))
    if response.status_code is 200:
        return response.json()
    else:
        return None


def get_url(url, data=None):
    response = requests.get(url, data)

    if response.status_code is 200:
        return response.json()
    else:
        return None


def send_mail(mailserver_data, recipient, mail_text):
    connection = smtplib.SMTP_SSL(mailserver_data["host"] + ":465")
    connection.login(mailserver_data["username"], mailserver_data["password"])
    connection.sendmail('from: ' + 'mgroenin@primusnetz.de', 'to: ' + recipient, mail_text)
    connection.quit()


def generate_mail_body_from_check(check_data):
    subject = 'Subject: Check %s on %s has changed to %s!\n' % (
        check_data["CheckID"],
        check_data["Node"],
        check_data["Status"]
    )
    msg_text = """
    We have a  check %s on System %s that has changed to %s.
    The check gives the Output:

    %s

    Please inspect!


    """ % (
        check_data["CheckID"],
        check_data["Node"],
        check_data["Status"],
        check_data["Output"]
    )
    print(subject + msg_text)
    return subject + msg_text


def main():
    print ("consul alerter running")
    while True:
        # endless loop because we have no internal state
        # and read configuration _every_ time from consul
        state = get_url(CONSUL + STATE_URL + "?raw")
        if not state:
            state = {
            }
        duration_value = get_url(CONSUL + DURATION_URL + "?raw")
        duration_default = 600

        if duration_value:
            duration = duration_value
        else:
            duration = duration_default
            post_url(CONSUL + DURATION_URL, duration)

        mailserver_data = get_url(CONSUL + MAILSERVER_URL)
        if not mailserver_data or not {"host", "username", "password", "sender","recipient"}.issubset(set(mailserver_data.keys())):
            print("Mail-Server setup at " + CONSUL +
                  MAILSERVER_URL + "not correct")
            exit(1)

        checks = get_url(CONSUL + CHECKS_URL)

        for key in checks.keys():
            check = checks[key]  # get one check from consul
            #if check["CheckID"] in state.keys():
            # get one check state from state
            try:
                check_state = state[check["CheckID"]]
            except KeyError:
                check_state = {
                    "last_alert": (datetime.datetime.now() - datetime.timedelta(seconds=duration)).isoformat(),
                    "Status": check["Status"],
                    "next_alert": datetime.datetime.now().isoformat()
                }
                state[check["CheckID"]] = check_state
                post_url(CONSUL + STATE_URL, state)
            if check_state["Status"] != check["Status"]:
                # check if check_state and check status differ or we
                # alerted more than $duration seconds ago
                print("%s: Check Status has changed from %s to %s " %( str(datetime.datetime.now().isoformat()),  check_state["Status"], check["Status"] ))
                send_mail(
                    mailserver_data,
                    mailserver_data["recipient"],
                    generate_mail_body_from_check(check)
                )
                check_state = {
                    "last_alert": datetime.datetime.now().isoformat(),
                    "Status": check["Status"],
                    "next_alert": (datetime.datetime.now() + datetime.timedelta(seconds=duration)).isoformat()
                }
                state[check["CheckID"]] = check_state
                post_url(CONSUL + STATE_URL, state)
            else:
                # get one check state from state
                check_state = state[check["CheckID"]]

                if check["Status"] != "passing" and datetime.datetime.now() > (parse(check_state["last_alert"]) + datetime.timedelta(seconds=duration)):
                    print("%s: Check Status is still%s " %( str(datetime.datetime.now().isoformat()), check["Status"] ))
                    send_mail(
                        mailserver_data,
                        mailserver_data["recipient"],
                        generate_mail_body_from_check(check)
                    )
                    check_state = {
                        "last_alert": datetime.datetime.now().isoformat(),
                        "Status": check["Status"],
                        "next_alert": (datetime.datetime.now() + datetime.timedelta(seconds=duration)).isoformat()
                    }
                    state[check["CheckID"]] = check_state
                    post_url(CONSUL + STATE_URL, state)

        time.sleep(10)


if __name__ == "__main__":
    main()
