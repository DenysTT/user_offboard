from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
import logging
import sys
import os
from api_applications.apps_api import IPA, AWS, GIT, SPOTINST
import json
import time
from datetime import datetime
import unidecode
import teams_notification
import collections

log = logging.getLogger('bamboo')
logpattern = '%(asctime)s %(levelname)s %(message)s'
log_handler = logging.StreamHandler()
log_handler.setFormatter(logging.Formatter(logpattern))
log.addHandler(log_handler)
log.setLevel(logging.DEBUG)

BASE_GIT_URL = os.environ.get('BASE_GIT_URL')
BASE_SPOT_URL = 'https://api.spotinst.io'
GIT_TOKEN = os.environ.get('GIT_TOKEN')

BAMBOO_USER = os.environ.get('BAMBOO_USER')
BAMBOO_PASSWORD = os.environ.get('BAMBOO_PASSWORD')

IPA_USER = os.environ.get('IPA_USER')
IPA_PASSWORD = os.environ.get('IPA_PASSWORD')

SPOTINST_TOKEN = os.environ.get('SPOTINST_TOKEN')

AWS_DEV_ID = os.environ.get('AWS_DEV_ID')
AWS_DEV_SECRET = os.environ.get('AWS_DEV_SECRET')

AWS_PLATFORM_ID = os.environ.get('AWS_PLATFORM_ID')
AWS_PLATFORM_SECRET = os.environ.get('AWS_PLATFORM_SECRET')

bamboo_base_url = os.environ.get('BAMBOO_BASE_URL')
bamboo_url_get_tasks = bamboo_base_url + "/inbox/offboarding"
bamboo_url_login = bamboo_base_url + "/login.php"

ipa_server_url = os.environ.get('IPA_SERVER_URL')


def main():
    teams_message = collections.defaultdict(list)
    aws_dev = AWS(AWS_DEV_ID, AWS_DEV_SECRET, "DEV")
    aws_platform = AWS(AWS_PLATFORM_ID, AWS_PLATFORM_SECRET, "PLATFORM")
    driver = webdriver.PhantomJS("/usr/local/bin/phantomjs")
    login_to_bamboo(driver)
    users = get_tasks(driver)
    user_names_with_dot = [unidecode.unidecode(name.replace(" ", ".")) for name in users]
    if users.__len__() == 0:
        log.info("There are no users to process")
        sys.exit(0)
    disable_users_in_ipa(user_names_with_dot, teams_message)
    disable_users_in_AWS([aws_dev, aws_platform], user_names_with_dot, teams_message)
    block_users_in_GIT(user_names_with_dot, teams_message)
    disable_users_in_SPOTINST(user_names_with_dot, teams_message)
    teams_notification.send_message(teams_message)
    remove_users_from_bamboo_dashboard(driver, users)
    driver.close()


def login_to_bamboo(driver):
    driver.set_window_size(1124, 850)
    driver.get(bamboo_url_login)
    driver.find_element_by_id(id_='lemail').send_keys(BAMBOO_USER)
    driver.find_element_by_name('password').send_keys(BAMBOO_PASSWORD)
    driver.find_element_by_css_selector(".login-actions > button").click()


def get_tasks(driver):
    driver.get(bamboo_url_get_tasks)
    names = []
    try:
        driver.find_element_by_class_name("MsgListing__textIcon")
    except NoSuchElementException:
        return names
    user_elements = driver.find_elements_by_class_name("MsgListing__flexContent")
    for element in user_elements:
        user_name = element.find_element_by_css_selector(".MsgListing__text")
        log.info("Processing User %s" % user_name.text)
        if not element.find_elements_by_css_selector(".MsgListing__note"):
            if user_name.text not in names: names.append(user_name.text)
            continue
        d = element.find_elements_by_css_selector(".MsgListing__note")[0].text.replace("–\n","")
        if d:
            remove_date = datetime.strptime(d, "%b %d, %Y").strftime("%Y-%m-%d")
            today_date = datetime.today().strftime("%Y-%m-%d")
        else:
            continue
        if today_date >= remove_date:
            if user_name.text not in names: names.append(user_name.text)
    return names


def remove_users_from_bamboo_dashboard(driver, names):
    elements = driver.find_elements_by_css_selector(".js-MsgListing__wrapper")
    counter = 0
    for x in range(len(elements)):
        elements = driver.find_elements_by_css_selector(".js-MsgListing__wrapper")
        user_name = elements[counter].find_element_by_css_selector(".MsgListing__text")
        if user_name.text in names:
            check_box = elements[counter].find_element_by_css_selector(".fab-Checkbox__label")
            check_box.click()
            time.sleep(5)
        else:
            counter += 1


def disable_users_in_ipa(users, teams_message):
    try:
        ipa = IPA(ipa_server_url, log)
        ipa.login(IPA_USER, IPA_PASSWORD)
        for user in users:
            user_name = user.replace(" ", ".")
            ipa_user = ipa.user_find(user_name)['result']
            if ipa_user['count'] == 0:
                log.info("%s user is absent in FreeIPA" % user)
                teams_message[user].append("user is absent in FreeIPA")
                continue
            rsp = ipa.user_disable(user_name)
            if 'error' in rsp and rsp['error'] is not None and 4010 == rsp['error']['code']:
                log.info("%s - %s" % (rsp['error']['message'], user))
                teams_message[user].append(rsp['error']['message'] + " in IPA")
            else:
                log.info(rsp['result']['summary'] + " in IPA")
                teams_message[user].append(rsp['result']['summary'] + " in IPA")
    except Exception as e:
        log.error(e)
        teams_notification.send_error_message(e)
        sys.exit(1)
    finally:
        ipa.session.close()


def disable_users_in_AWS(clients, users, teams_message):
    for client in clients:
        for user in users:
            try:
                client.get_user(user)
            except client.client.exceptions.NoSuchEntityException:
                log.info("%s user is absent in AWS %s account" % (user, client.account_name))
                teams_message[user].append("Absent in AWS %s account" % client.account_name)
                continue
            except Exception as e:
                log.error(e)
                teams_notification.send_error_message(e)
                sys.exit(1)
            access_keys = client.get_list_access_keys(user)
            for access_key in access_keys['AccessKeyMetadata']:
                rsp = client.disable_user_access_key(user, access_key['AccessKeyId'])
                if rsp['ResponseMetadata']['HTTPStatusCode'] == 200:
                    log.info("access key %s has been disabled for %s user" % (access_key, user))
                    teams_message[user].append("access key %s has been disabled " % access_key)
            try:
                client.delete_user_login_profile(user)
                log.info("AWS %s console access has been disabled for %s user" % (client.account_name, user))
                teams_message[user].append("AWS %s console access has been disabled" % client.account_name)
            except client.client.exceptions.NoSuchEntityException:
                log.info("%s user is already blocked in AWS %s account" % (user, client.account_name))
                teams_message[user].append("Already blocked in AWS %s account" % client.account_name)
                continue
            except Exception as e:
                log.error(e)
                teams_notification.send_error_message(e)
                sys.exit(1)


def disable_users_in_SPOTINST(users, teams_message):
    spotinst = SPOTINST(BASE_SPOT_URL, SPOTINST_TOKEN)
    for user in users:
        user_rsp = spotinst.get_spot_user(user)
        if user_rsp.status_code is not 200:
            log.info("%s user is absent in Spotinst" % (user))
            teams_message[user].append("Absent in Spotinst")
            continue
        user_dict = json.loads(user_rsp.text)
        for account in user_dict['response']['items']:
            spotinst.delete_spot_user_from_account(account['accountId'], user)
            log.info("AccountID %s access in Spot.io has been disabled for %s user" % (account['accountId'], user))
            teams_message[user].append("AccountID %s access in Spot.io has been disabled" % account['accountId'])


def block_users_in_GIT(users, teams_message):
    git = GIT(BASE_GIT_URL, GIT_TOKEN)
    for user in users:
        try:
            user_rsp = git.get_gitlab_user(user)
            if user_rsp.text == '[]':
                log.info("%s user is absent in GIT" % (user))
                teams_message[user].append("Absent in GIT")
                continue
            user_dict = json.loads(user_rsp.text)
            if 'id' in user_dict[0].keys():
                rsp = git.block_gitlab_user(user_dict[0]['id'])
                if rsp.text == "false":
                    log.info("%s user already blocked in GIT" % (user))
                    teams_message[user].append("already blocked in GIT")
                else:
                    log.info("%s user blocked in GIT" % (user))
                    teams_message[user].append("User blocked in GIT")
        except Exception as e:
            log.error(e)
            teams_notification.send_error_message(e)
            sys.exit(1)


if __name__ == "__main__":
    main()
