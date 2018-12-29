import os
import json
import re
import yaml
import time
import tornado.ioloop
import tornado.web
from pykafka import KafkaClient


class GithubHookHandler(tornado.web.RequestHandler):
    def initialize(self, kafka_producer):
        self.kafka_producer = kafka_producer

    async def send_response(self, data, status=200):
        self.set_status(status)
        self.write(json.dumps(data))

    async def parse_commits(self, commits):
        prefixes = ['US', 'S', 'DE', 'F']
        commits_with_FIDs = []
        messages = [commit['message'] for commit in commits]
        fid_pattern = r'\b((%s)\d+)\b' % '|'.join(prefixes)
        for message in messages:
            results = re.findall(fid_pattern, message, re.IGNORECASE)
            if results:
                commits_with_FIDs.append([item[0].upper() for item in results])
        return commits_with_FIDs

    async def post(self):
        post_data = self.get_argument("payload")
        payload = json.loads(post_data)
        if await self.parse_commits(payload['commits']):
            print("will be posting to a kafka topic")
            self.kafka_producer.produce(post_data.encode())
        else:
            print("will NOT be posting to a kafka topic")
        print(post_data)
        await self.send_response({'msg': 'ok'}, status=200)


def read_config(config_path):
    with open(config_path, 'r') as cf:
        content = cf.read()
        conf = yaml.load(content)
    return conf

def make_app():
    config = read_config('configs/kafka_config.yml')
    kafka_home = config.get('KafkaHome')
    topic_name = config.get('TopicName')
    hosts = config.get('Hosts', 'localhost:9092')
    replication_factor = config.get('Replication', 1)
    partitions = config.get('Partitions', 1)
    zookeeper  = config.get('Zookeeper', 'localhost:2181')
    kafka_client = KafkaClient(hosts=hosts)
    cmd = "%s/%s/bin/kafka-topics.sh" % (os.environ['HOME'], kafka_home)

    kafka_topic = kafka_client.topics[b'%s' % topic_name.encode()]
    if not kafka_topic:
        os.system("%s --create --zookeeper %s --replication-factor %s --partitions %s --topic %s"
                  % (cmd, zookeeper, replication_factor, partitions, topic_name ))
    time.sleep(3)

    kafka_producer = kafka_topic.get_producer()
    return tornado.web.Application([
        (r"/", GithubHookHandler, dict(kafka_producer=kafka_producer, )),
    ])

if __name__ == "__main__":
    app = make_app()
    app.listen(48888)
    tornado.ioloop.IOLoop.current().start()