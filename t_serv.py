import os
import json
import re
import tornado.ioloop
import tornado.web


class GithubHookHandler(tornado.web.RequestHandler):

    def send_response(self, data, status=200):
        self.set_status(status)
        self.write(json.dumps(data))

    def parse_commits(self, commits):
        prefixes = ['US', 'S', 'DE', 'F']
        commits_with_FIDs = []
        messages = [commit['message'] for commit in commits]
        fid_pattern = r'\b((%s)\d+)\b' % '|'.join(prefixes)
        for message in messages:
            results = re.findall(fid_pattern, message, re.IGNORECASE)
            if results:
                commits_with_FIDs.append([item[0].upper() for item in results])
        return commits_with_FIDs

    def post(self):
        post_data = self.get_argument("payload")
        print("got a message of type %s from GitHub..." % type(post_data))
        payload = json.loads(post_data)
        if self.parse_commits(payload['commits']):
            print("will be posting to a kafka topic")
        else:
            print("will NOT be posting to a kafka topic")
        print(post_data)
        self.send_response({'msg': 'ok'}, status=200)

def make_app():
    return tornado.web.Application([
        (r"/", GithubHookHandler),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(48888)
    tornado.ioloop.IOLoop.current().start()