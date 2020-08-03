import requests
import json
import boto3


class IPA(object):

    def __init__(self, server, log, sslverify=False):
        self.server = server
        self.sslverify = sslverify
        self.log = log
        self.session = requests.session()

    def login(self, user, password):
        rv = None
        ipaurl = 'https://{0}/ipa/session/login_password'.format(self.server)
        header = {'referer': ipaurl, 'Content-Type':
                  'application/x-www-form-urlencoded', 'Accept': 'text/plain'}
        login = {'user': user, 'password': password}
        rv = self.session.post(ipaurl, headers=header, data=login,
                               verify=self.sslverify)

        if rv.status_code != 200:
            self.log.warning('Failed to log {0} in to {1}'.format(
                user,
                self.server)
            )
            rv = None
        else:
            # set login_user for use when changing password for self
            self.login_user = user
        return rv

    def makeReq(self, pdict):
        results = None
        ipaurl = 'https://{0}/ipa'.format(self.server)
        session_url = '{0}/session/json'.format(ipaurl)
        header = {'referer': ipaurl, 'Content-Type': 'application/json',
                  'Accept': 'application/json'}

        data = {'id': 0, 'method': pdict['method'], 'params':
                [pdict['item'], pdict['params']]}

        request = self.session.post(
                session_url, headers=header,
                data=json.dumps(data),
                verify=self.sslverify
        )
        results = request.json()

        return results

    def user_find(self, user=None, attrs={}, sizelimit=40000):
        params = {'all': True,
                  'no_members': False,
                  'sizelimit': sizelimit,
                  'whoami': False}
        params.update(attrs)
        m = {'item': [user], 'method': 'user_find', 'params': params}
        results = self.makeReq(m)

        return results

    def user_status(self, user):
        m = {'item': [user], 'method': 'user_status', 'params':
             {'all': True, 'raw': False}}
        results = self.makeReq(m)

        return results

    def user_disable(self, user):
        m = {'item': [user], 'method': 'user_disable', 'params':
             {'version': '2.49'}}
        results = self.makeReq(m)
        return results


class AWS(object):

    def __init__(self, key_id, secret_key, account_name):
        self.client = boto3.client('iam', aws_access_key_id=key_id, aws_secret_access_key=secret_key)
        self.account_name = account_name

    def get_user(self, user):
        return self.client.get_user(UserName=user)

    def get_list_access_keys(self, user):
        return self.client.list_access_keys(UserName=user)

    def disable_user_access_key(self, user, key_id):
        return self.client.update_access_key(AccessKeyId=key_id, Status="Inactive", UserName=user)

    def delete_user_login_profile(self, user):
        self.client.delete_login_profile(UserName=user)


class SPOTINST(object):

    def __init__(self, server, token):
        self.server = server
        self.token = token

    def get_spot_user(self, user):
        spotinst_url = "%s/setup/accountUserMapping?userEmail=%s" % (self.server, user)
        rsp = requests.get(spotinst_url,
                           headers={"Content-Type": "application/json",
                                    "Authorization": "Bearer " + self.token})
        return rsp

    def delete_spot_user_from_account(self, account_id, user):
        git_lab_url = "%s/setup/account/%s/user/" % (self.server, account_id)
        rsp = requests.delete(git_lab_url,
                              json={'userEmail': user},
                              headers={"Content-Type": "application/json",
                                       "Authorization": "Bearer " + self.token})
        return rsp


class GIT(object):
    def __init__(self, server, token):
        self.server = server
        self.token = token

    def get_gitlab_user(self, user):
        git_lab_url = "%s/users?username=%s" % (self.server, user)
        rsp = requests.get(git_lab_url,
                           headers={'PRIVATE-TOKEN': self.token})
        return rsp

    def block_gitlab_user(self, user_id):
        git_lab_url = "%s/users/%s/block" % (self.server, user_id)
        rsp = requests.post(git_lab_url,
                            headers={'PRIVATE-TOKEN': self.token})
        return rsp
