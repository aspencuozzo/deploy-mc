# Server.py communicates with Docker and MySQL to do actions and return relevant data to script.py
# Last updated: October 6, 2019
import docker
import asyncio
import aiohttp
import aiofiles
import base64
import requests
import os
import json
import mcstatus
import traceback
import shutil
import urllib.request
import mysql.connector
import nest_asyncio
import subprocess
import zlib
import zipfile
from b2sdk.v1 import *

nest_asyncio.apply()
client = docker.from_env()
info = InMemoryAccountInfo()

b2_api = B2Api(info)
application_key = 'YOUR_APP_KEY'
application_key_id = 'YOUR_APP_KEY_ID'
b2_api.authorize_account("production", application_key_id, application_key)

db_user = 'YOUR_DB_USER'
db_pass = 'YOUR_DB_USER_PASS'
db_name = 'YOUR_DB_NAME'

def get_b2_auth():
    """Gets auth token from B2 API for uploading and downloading server data"""
    flagDebug = False
    b2AppKey = b'YOUR_APP_KEY'
    b2AppKeyId = b'YOUR_APP_KEY_ID'
    baseAuthorizationUrl = 'https://api.backblazeb2.com/b2api/v2/b2_authorize_account'
    b2GetDownloadAuthApi = '/b2api/v2/b2_get_download_authorization'

    idAndKey = b2AppKeyId + b':' + b2AppKey
    b2AuthKeyAndId = base64.b64encode(idAndKey)
    basicAuthString = 'Basic ' + b2AuthKeyAndId.decode('UTF-8')
    authorizationHeaders = {'Authorization' : basicAuthString}

    resp = requests.get(baseAuthorizationUrl, headers=authorizationHeaders)

    if flagDebug:
        print (resp.status_code)
        print (resp.headers)
        print (resp.content)

    respData = json.loads(resp.content)
    bAuToken = respData["authorizationToken"]
    bFileDownloadUrl = respData["downloadUrl"]
    bPartSize = respData["recommendedPartSize"]
    bApiUrl = respData["apiUrl"]

    return bAuToken

def gets_container(usesContainer):
    """Decorator function to automatically handle returning error in case container does not exist"""
    def getContainer(*args, **kwargs):
        try:
            kwargs["container"] = client.containers.get(kwargs["container"])
        except docker.errors.NotFound:
            return ("failure", "container not found")
        else:
            return usesContainer(*args, **kwargs)
    return getContainer

class DockerCommandServer(asyncio.Protocol):
    def connection_made(self, transport):
        self.commands = {"list": self.list_containers, 
                        "start": self.start_container,
                        "stop": self.stop_container,
                        "delete": self.delete_container,
                        "status": self.container_status,
                        "create": self.create_container,
                        "inject": self.execute_console_command,
                        "request": self.return_requested,
                        "balance": self.balance_tools}
        self.transport = transport

    # received model: {"command": "<command>", "args": <dict of args>}
    # sent model: {"status": "<status", "result": "<result>"}
    def data_received(self, data):
        message = json.loads(data.decode())
        command = message["command"]
        kwargs = message["args"]
        returnDict = dict()
        try:
            status, value = self.commands[command](**kwargs)
        except Exception as e:
            returnDict["status"] = "failure"
            returnDict["result"] = None
            print(traceback.print_exc()) # TODO: better error handling than this
        else:
            returnDict["status"] = status
            returnDict["result"] = value
        self.transport.write(json.dumps(returnDict).encode("utf-8"))

    def list_containers(self):
        """Returns a list of containers."""
        return ("success", [str(container) for container in client.containers.list()])
    
    @gets_container
    def start_container(self, container, friendly_name):
        """Starts the given container."""
        mysql_connection = mysql.connector.connect(user=db_user, password=db_pass, database=db_name, autocommit=True)
        cursor = mysql_connection.cursor()

        # Check if container is already up
        cursor.execute("SELECT status FROM instances WHERE name = %s", (str(friendly_name),))
        result = cursor.fetchall()
        status_inst_list = [list(i) for i in result]
        status_inst = str(status_inst_list).strip("[]()',")

        if (status_inst == 'stopped'):
            ## B2 stuff
            token = get_b2_auth()
            file_name = "/home/discord/deploymc/instances/" + friendly_name + ".zip"
            file_url = "https://files.cosmopath.com/file/Deploy-B2-01/" + friendly_name + ".zip?Authorization=" + token
            print(file_url)
            
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-agent', 'Mozilla/5.0')]
            urllib.request.install_opener(opener)
            urllib.request.urlretrieve(file_url, file_name)

            # shutil.unpack_archive(file_name, '/home/discord/deploymc/instances/')
            zipfile.ZipFile(file_name).extractall("/home/discord/deploymc/instances/")

            # Delete
            file_name_np = friendly_name + ".zip"
            bucket = b2_api.get_bucket_by_name('Deploy-B2-01')
            for file_info, folder_name in bucket.ls(show_versions=False):
                if (file_info.file_name == file_name_np): 
                    file_id = str(file_info.id_)
                    print(file_id)
                    b2_api.delete_file_version(file_id, file_name_np)
            os.remove(file_name)
            
            # Docker and DB stuff
            container.start()
            cursor.execute("UPDATE instances SET status = 'running' WHERE container_id = %s", (str(container.id),))
            mysql_connection.commit()
            mysql_connection.close()
            return ("success", "started")

        elif (status_inst == 'running'):
            return ("success", "already started")

        elif (status_inst == 'insufficient funds'):
            return ("success", "insufficient funds")
    
    @gets_container
    def stop_container(self, container, friendly_name):
        """Stops the given container."""
        # Check if container is already up
        mysql_connection = mysql.connector.connect(user=db_user, password=db_pass, database=db_name, autocommit=True)
        cursor = mysql_connection.cursor()
        cursor.execute("SELECT status FROM instances WHERE name = %s", (str(friendly_name),))
        result = cursor.fetchall()
        status_inst_list = [list(i) for i in result]
        status_inst = str(status_inst_list).strip("[]()',")

        if (status_inst == 'running'):
            # Docker and DB stuff
            container.stop()
            cursor.execute("UPDATE instances SET status = 'stopped' WHERE container_id = %s", (str(container.id),))
            mysql_connection.commit()
            mysql_connection.close()

            # Making .zip of server data
            local_path = '/home/discord/deploymc/instances/' + friendly_name
            b2_file_name = friendly_name + ".zip"
            shutil.make_archive(local_path, 'zip', local_path)
            def zipdir(path, zip):
                path = os.path.abspath(path)
                for root, dirs, files in os.walk(path):
                    dest_dir = root.replace(os.path.dirname(path), '', 1)
                    for file in files:
                        zip.write(os.path.join(root, file), arcname=os.path.join(dest_dir, file))
            zipf = zipfile.ZipFile('/home/discord/deploymc/instances/' + b2_file_name, 'w', zipfile.ZIP_STORED)
            zipdir(local_path, zipf)
            zipf.close()

            # B2 stuff
            bucket = b2_api.get_bucket_by_name('Deploy-B2-01')
            bucket.upload_local_file(local_file=local_path+".zip", file_name = b2_file_name)

            # Delete zip and dir after uploaded
            os.remove(local_path + ".zip")
            shutil.rmtree(local_path)

            return ("success", "stopped")
        
        elif (status_inst == 'stopped'):
            return ("success", "already stopped")

    @gets_container
    def delete_container(self, container, name):
        """Deletes the given container."""
        
        # Stop container and remove directory
        def rmdir(dir_name):
            path = '/home/discord/deploymc/instances/' + dir_name
            if os.path.isdir(path):
                shutil.rmtree(path)
        container.stop()
        container.remove(v=True)
        rmdir(name)

        # Remove row in DB
        mysql_connection = mysql.connector.connect(user=db_user, password=db_pass, database=db_name, autocommit=True)
        cursor = mysql_connection.cursor()
        sql_delete = ("DELETE FROM instances WHERE name = %s")
        sql_data = (name,)
        cursor.execute(sql_delete, sql_data)
        mysql_connection.commit()
        mysql_connection.close()

        # Delete file from B2
        file_name = name + ".zip"
        bucket = b2_api.get_bucket_by_name('Deploy-B2-01')
        for file_info, folder_name in bucket.ls(show_versions=False):
            if (file_info.file_name == file_name): 
                file_id = file_info.id_
                b2_api.delete_file_version(file_id, file_name)
        
        return ("success", None)

    def create_container(self, name, owner, game, memory, port, server_type=None, version=None):
        """Creates a new container."""
        # Init DB connection
        mysql_connection = mysql.connector.connect(user=db_user, password=db_pass, database=db_name, autocommit=True)
        cursor = mysql_connection.cursor()

        # Get balance of user
        cursor.execute("SELECT balance FROM accounts WHERE discord_id = %s", (str(owner),))
        result = cursor.fetchall()
        balance_list = [list(i) for i in result]
        balance_str = str(balance_list).strip('[](),')
        balance = float(balance_str)

        # Get price of desired instance (will be updated later)
        if (game == 'JAVA'):
            price = 0.00685
        elif (game == 'BEDROCK'):
            price = 0.00342
        
        # See if user can afford instance, if so do all the stuff
        if (price < balance):
            def mkdir(dir_name):
                path = '/home/discord/deploymc/instances/' + dir_name
                try:
                    os.mkdir(path)
                except OSError:
                    print ("Creation of the directory %s failed" % path)
                else:
                    print ("Successfully created the directory %s " % path)
            mkdir(name)

            if (game == 'JAVA'):
                portlist={"25565/tcp":port}
                if (server_type == "VANILLA"):
                    inst_type = "VANILLA-1GB"
                    environment={"VERSION": version, "EULA": "TRUE"}
                    if (version == '1.13.2' or version == '1.14.4'):
                        memory = '1500M'
                        inst_type = "VANILLA-1.5GB"
                else: 
                    inst_type = "PAPER-1GB"
                    environment={"MEMORY": "512M", "TYPE": server_type, "VERSION": version, "EULA": "TRUE"}
                #mkdir(name)
                container = client.containers.run('itzg/minecraft-server', command="--noconsole", user=1003, mem_limit=memory, ports=portlist, name=name, 
                            detach=True, volumes = {'/home/discord/deploymc/instances/' + name: {'bind': '/data', 'mode': 'rw'}}, environment=environment)
            elif (game == 'BEDROCK'):
                portlist={"19132/udp":port}
                environment={"EULA": "TRUE"}
                inst_type = "BEDROCK-1GB"
                # mkdir(name)
                container = client.containers.run('itzg/minecraft-bedrock-server', command="--noconsole", mem_reservation=memory, ports=portlist, name=name, 
                            detach=True, volumes = {'/home/discord/deploymc/instances/' + name: {'bind': '/data', 'mode': 'rw'}}, environment=environment)
            # elif (game == 'CUBERITE'):
            #     portlist={"25565/tcp":port1, "8080/tcp":port2}
            #     environment={"ADMIN_PASSWORD": admin_password}
            #     container = client.containers.run('beevelop/cuberite', tty = True, mem_reservation=memory, ports=portlist, name=name, detach=True, environment=environment)
            cursor.execute("INSERT INTO instances(name,owner,container_id,type,status,port) VALUES (%s,%s,%s,%s,%s,%s)", (name, owner, str(container.id), inst_type, "running", str(port)))
            mysql_connection.commit()
            mysql_connection.close()
            return ("success", "created")
        else:
            mysql_connection.close()
            return ("success", "insufficient funds")

    @gets_container
    def container_status(self, container):
        """Returns status information about the container."""
        full_stats = container.stats(stream=False)
        status = container.status
        if status != "running":
            return ("success",
            {
                "status": status
            })
        external_port = container.attrs["NetworkSettings"]["Ports"]["25565/tcp"][0]["HostPort"]
        minecraft_status = mcstatus.MinecraftServer("localhost", int(external_port)).status()
        return ("success",
        {
            "status": status,
            "players": {"online": minecraft_status.players.online,
                        "max": minecraft_status.players.max},
            "version": minecraft_status.version.name,
            "description": minecraft_status.description,
            "ram_usage": full_stats["memory_stats"]["usage"],
        })
    
    @gets_container
    def execute_console_command(self, container, injectcommand):
        container.exec_run("rcon-cli " + injectcommand)
        return ("success", None)

    def return_requested(self, request, name=None, owner=None):
        final_result = None
        mysql_connection = mysql.connector.connect(user=db_user, password=db_pass, database=db_name, autocommit=True)
        cursor = mysql_connection.cursor()
        if (request == 'name'):
            cursor.execute("SELECT name FROM instances WHERE owner = %s", (str(owner),))
            result = cursor.fetchall()
            final_result = [list(i) for i in result]
        elif (request == 'port'):
            cursor.execute("SELECT port FROM instances WHERE name = %s", (str(name),))
            result = cursor.fetchall()
            final_result = [list(i) for i in result]
        mysql_connection.close()
        return ("success", final_result)

    def balance_tools(self, action, name):
        in_db = 0  # 0 = false, 1 = true
        mysql_connection = mysql.connector.connect(user=db_user, password=db_pass, database=db_name, autocommit=True)
        cursor = mysql_connection.cursor()
        # Load balance (currently preset for testing)
        if (action == 'load'):
            cursor.execute("SELECT discord_id FROM accounts")
            result = cursor.fetchall()
            discord_id_list = [list(i) for i in result]
            for x in discord_id_list:
                match_name = str(x).strip("[]()'',")
                if match_name == name:
                    in_db = 1
            if in_db == 0:
                cursor.execute("INSERT INTO accounts(discord_id, balance) VALUES (%s, %s)", (str(name), '0.33'))
                mysql_connection.commit()
                return ("success", "loaded")
            elif (in_db == 1):
                return ("success", "duplicate")
        # Check balance
        if (action == 'check'):
            cursor.execute("SELECT balance FROM accounts WHERE discord_id = %s", (str(name),))
            result = cursor.fetchall()
            balance_list = [list(i) for i in result]
            balance_str = str(balance_list).strip('[](),')
            return ("success", balance_str)
        mysql_connection.close()
        return ("success", None)

# definitely didn't steal this section from the python documentation
loop = asyncio.get_event_loop()
coro = loop.create_unix_server(DockerCommandServer, "/tmp/docker.socket")
server = loop.run_until_complete(coro)
os.chown("/tmp/docker.socket", 1003, 1006)
os.chmod("/tmp/docker.socket", 0o770)

# Serve requests until Ctrl+C is pressed
print('Serving on {}'.format(server.sockets[0].getsockname()))
try:
    loop.run_forever()
except KeyboardInterrupt:
    pass

# Close the server
server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
