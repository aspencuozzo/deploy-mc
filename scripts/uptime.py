import docker
import datetime
import pytz
from dateutil import parser
import mysql.connector

client = docker.from_env()
mysql_connection = mysql.connector.connect(user='runner', password='ZNZRQW3TC3FF', database='deploymc')
cursor = mysql_connection.cursor()
utc = pytz.UTC

def uptime(container):
    startTime = parser.isoparse(container.attrs['State']['StartedAt'])
    uptime = utc.localize(datetime.datetime.now()) - startTime
    uptime_mins = uptime.seconds/60
    cursor.execute("UPDATE instances SET uptime = %s WHERE container_id = %s", (str(uptime_mins), str(container.id)))
    mysql_connection.commit()
    print("Uptime refreshed.")

for container in client.containers.list():
    uptime(container)