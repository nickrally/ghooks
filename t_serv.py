import os
import time
import yaml
import tornado.ioloop
import tornado.web
import aiopg
import psycopg2
from gh_handlers import  GithubHookHandler, GithubHomeHandler, GithubSetupHandler
from tornado.options import define, options
import tornado.locks
from pykafka import KafkaClient


define("db_database", default="installations", help="database name")
define("db_host",     default="127.0.0.1",     help="database host")
define("db_port",     default=5432,            help="database port")
define("db_user",     default="pairing",       help="database user")
define("db_password", default="pairing",       help="database password")

def read_config(config_path):
    with open(config_path, 'r') as cf:
        content = cf.read()
        conf = yaml.load(content)
    return conf

def kafka():
    config = read_config('configs/kafka_config.yml')
    kafka_home = config.get('KafkaHome')
    topic_name = config.get('TopicName')
    hosts = config.get('Hosts', 'localhost:9092')
    replication_factor = config.get('Replication', 1)
    partitions = config.get('Partitions', 1)
    zookeeper = config.get('Zookeeper', 'localhost:2181')
    kafka_client = KafkaClient(hosts=hosts)
    cmd = "%s/%s/bin/kafka-topics.sh" % (os.environ['HOME'], kafka_home)

    kafka_topic = kafka_client.topics[b'%s' % topic_name.encode()]
    if not kafka_topic:
        os.system("%s --create --zookeeper %s --replication-factor %s --partitions %s --topic %s"
                  % (cmd, zookeeper, replication_factor, partitions, topic_name))
    time.sleep(3)

    return kafka_topic.get_producer()

ROUTES = [ (r"/",             GithubHookHandler, dict(kafka_producer=kafka(), )),
           (r"/home",         GithubHomeHandler),
           (r"/setup",        GithubSetupHandler),
           (r"/setup_result", GithubSetupHandler)
         ]

async def maybe_create_table(db):
    try:
        with (await db.cursor()) as cur:
            await cur.execute("SELECT COUNT(*) FROM installation LIMIT 1")
            await cur.fetchone()
    except psycopg2.ProgrammingError:
        with open("schema.sql") as f:
            schema = f.read()
        with (await db.cursor()) as cur:
            await cur.execute(schema)


class GitHubApplication(tornado.web.Application):
    def __init__(self, handlers, db):
        self.db = db

        settings = dict(
            blog_title=u"Github App for Rally",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            #ui_modules={"Entry": EntryModule},
            xsrf_cookies=False,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/auth/login",
            debug=True,
        )
        super().__init__(handlers, **settings)

##############################################################################################

async def main():

    async with aiopg.create_pool(
            host=options.db_host,
            port=options.db_port,
            user=options.db_user,
            password=options.db_password,
            dbname=options.db_database) as db:
        await maybe_create_table(db)

        app = GitHubApplication(ROUTES, db)
        app.listen(7888)
        shutdown_event = tornado.locks.Event()
        await shutdown_event.wait()

    tornado.ioloop.IOLoop.current().start()

##############################################################################################
##############################################################################################


if __name__ == "__main__":
    #main()
    tornado.ioloop.IOLoop.current().run_sync(main)

