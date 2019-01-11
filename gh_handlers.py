import os
import re
import json
import tornado
import hmac
import hashlib
import pprint
from pyral import Rally

HOOK_SECRET_KEY = os.environb[b'HOOK_SECRET_KEY']

class NoResultError(Exception):
    pass

class GithubHookHandler(tornado.web.RequestHandler):

    def _validate_signature(self, data):
        sha_name, signature = self.request.headers._dict['X-Hub-Signature'].split('=')
        if sha_name != 'sha1':
            return False

        # HMAC requires its key to be bytes, but data is strings.
        mac = hmac.new(HOOK_SECRET_KEY, msg=data, digestmod=hashlib.sha1)
        return hmac.compare_digest(mac.hexdigest(), signature)

    def send_response(self, data, status=200):
        self.set_status(status)
        self.write(json.dumps(data))

    # def parse_commits(self, commits):
    #     prefixes = ['US', 'S', 'DE', 'F']
    #     commits_with_FIDs = []
    #     messages = [commit['message'] for commit in commits]
    #     fid_pattern = r'\b((%s)\d+)\b' % '|'.join(prefixes)
    #     for message in messages:
    #         results = re.findall(fid_pattern, message, re.IGNORECASE)
    #         if results:
    #             commits_with_FIDs.append([item[0].upper() for item in results])
    #     return commits_with_FIDs

    def post(self):
        post_data = self.request.body
        if not self._validate_signature(post_data):
            self.send_response(401)
            return
        print("got a message of type %s from GitHub..." % type(post_data))
        payload = json.loads(post_data)
        # if self.parse_commits(payload['commits']):
        #     print("will be posting to a kafka topic")
        # else:
        #     print("will NOT be posting to a kafka topic")
        pprint.pprint(payload)
        self.send_response({'msg': 'ok'}, status=200)


class  GithubHomeHandler(GithubHookHandler):
    def get(self):
        self.render("home.html")

class GithubSetupHandler(tornado.web.RequestHandler):
    async def query(self, stmt, *args):
        with (await self.application.db.cursor()) as cur:
            await cur.execute(stmt, args)
            return [self.row_to_obj(row, cur) for row in await cur.fetchall()]

    async def queryone(self, stmt, *args):
        """Query for exactly one result.
        Raises NoResultError if there are no results, or ValueError if
        there are more than one.
        """
        results = await self.query(stmt, *args)
        if len(results) == 0:
            raise NoResultError()
        elif len(results) > 1:
            raise ValueError("Expected 1 result, got %d" % len(results))
        return results[0]

    async def execute(self, stmt, *args):
        """Execute a SQL statement.
        Must be called with ``await self.execute(...)``
        """
        with (await self.application.db.cursor()) as cur:
            await cur.execute(stmt, args)

    def row_to_obj(self, row, cur):
        """Convert a SQL row to an object supporting dict and attribute access."""
        obj = tornado.util.ObjectDict()
        for val, desc in zip(row, cur.description):
            obj[desc.name] = val
        return obj

    async def match_user_subid(self, apikey, subid, install_id):
        try:
            rally = Rally("rally1.rallydev.com", apikey=apikey)
            fields = "SubscriptionID"
            user = rally.get('User', fetch=fields, instance=True)
            if user and user.SubscriptionID == int(subid):
                return True
            return False
        except Exception as ex:
            message = "Problem connecting to Rally. " + str(ex)
            self.render("setup_result.html", message=message, installid=install_id)


    async def get(self):
        # if 'Referer' not in self.request.headers or self.request.headers['Referer'] != "'https://github.com/'":
        #     print("bad referer")
        #     return

        install_id = self.get_argument("installation_id")
        try:
            app_instance = await self.queryone("SELECT * FROM installation WHERE install_id = %s", int(install_id))
        except NoResultError:
            await self.execute("INSERT INTO installation (install_id)" "VALUES (%s)", install_id)

        self.render("setup.html", installid=install_id)


    async def post(self):
        install_id = self.get_argument("installid")
        sub_id     = self.get_argument("subid")
        api_key    = self.get_argument("apikey")
        message    = ""
        try:
            app_instance = await self.queryone("SELECT * FROM installation WHERE install_id = %s", int(install_id))
        except NoResultError:
            raise tornado.web.HTTPError(404)

        if (await self.match_user_subid(api_key, sub_id, install_id)):
            await self.execute(
                "UPDATE installation SET sub_id = %s, api_key = %s "
                "WHERE install_id = %s",
                sub_id,
                api_key,
                int(install_id),
            )
            message = "record successfully written"
        else:
            message = "Apikey and SubscriptionID do not match"
        self.render("setup_result.html", message=message, installid=install_id)
